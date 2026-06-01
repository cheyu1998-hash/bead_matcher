"""库存业务逻辑：制作图案、撤销操作等高层封装。"""

from bead_matcher.dao.inventory_dao import InventoryDao
from bead_matcher.dao.make_record_dao import MakeRecordDao
from bead_matcher.inventory import Inventory
from bead_matcher.pattern import Pattern


def make_pattern(pattern: Pattern, copies: int = 1, note: str = "") -> dict:
    """
    制作图案：检查库存 -> 扣库存 -> 记流水 -> 记制作历史。

    Args:
        copies: 制作份数（默认 1）

    Returns:
        {"ok": True, "record_id": int, "consumed": dict}
        或 {"ok": False, "error": str}
    """
    if copies < 1:
        return {"ok": False, "error": "份数至少为 1"}

    inv_dao = InventoryDao()
    inv = inv_dao.load_inventory()
    if not inv:
        return {"ok": False, "error": "尚未初始化库存"}

    if inv.brand != pattern.brand:
        return {
            "ok": False,
            "error": f"库存品牌 {inv.brand} 与图案品牌 {pattern.brand} 不一致",
        }

    # 检查库存（考虑份数）
    inventory_qty = {code: inv.get_quantity(code) for code in inv.list_codes()}
    shortage = {}
    for code, need in pattern.color_usage.items():
        have = inventory_qty.get(code, 0)
        total_need = need * copies
        if have < total_need:
            shortage[code] = total_need - have

    if shortage:
        missing = sum(shortage.values())
        codes = ", ".join(shortage.keys())
        return {"ok": False, "error": f"库存不足，缺 {missing} 粒（色号: {codes}）"}

    # 创建制作前快照
    inv_dao.create_snapshot(inv, trigger="before_make", note=f"制作 {pattern.name} x{copies}")

    # 扣库存
    consumed: dict = {}
    for code, need in pattern.color_usage.items():
        total_need = need * copies
        inv.remove(code, total_need)
        consumed[code] = total_need

    # 保存库存
    inv_dao.save_inventory(inv)

    # 创建制作记录（附带份数元数据）
    consumed_with_meta = dict(consumed)
    consumed_with_meta["__copies__"] = copies
    consumed_with_meta["__per_copy__"] = dict(pattern.color_usage)

    make_dao = MakeRecordDao()
    record_id = make_dao.create(
        pattern_id=pattern.id,
        consumed=consumed_with_meta,
        status="done",
        note=note or f"制作 {pattern.name} x{copies}",
    )

    # 记流水
    inv2 = inv_dao.load_inventory()
    for code, need in consumed.items():
        balance = inv2.get_quantity(code)
        inv_dao.add_transaction(
            code=code,
            delta=-need,
            balance=balance,
            tx_type="make_consume",
            ref_id=record_id,
            note=f"制作 {pattern.name} x{copies}",
        )

    return {"ok": True, "record_id": record_id, "consumed": consumed}


def undo_last_operation() -> dict:
    """
    撤销上一条（或上一组）库存操作。

    - add / remove：单条撤销
    - make_consume：按 ref_id 找到同一批全部事务，整体撤销
    - set：不支持撤销（缺少前值）
    - rollback：不支持连续撤销

    Returns:
        {"ok": True, "undone": list}
        或 {"ok": False, "error": str}
    """
    inv_dao = InventoryDao()
    txs = inv_dao.list_transactions(limit=1)
    if not txs:
        return {"ok": False, "error": "没有可撤销的操作"}

    last_tx = txs[0]
    tx_type = last_tx["tx_type"]
    code = last_tx["code"]
    delta = last_tx["delta"]
    ref_id = last_tx.get("ref_id")

    if tx_type == "rollback":
        return {"ok": False, "error": "无法连续撤销"}

    if tx_type == "set":
        return {"ok": False, "error": "无法撤销 set 操作（缺少前值信息）"}

    inv = inv_dao.load_inventory()
    if not inv:
        return {"ok": False, "error": "库存未初始化"}

    undone = []

    if tx_type == "make_consume" and ref_id:
        # 撤销整批制作消耗
        batch_txs = inv_dao.list_transactions(limit=1000)
        batch_txs = [t for t in batch_txs if t.get("ref_id") == ref_id and t["tx_type"] == "make_consume"]
        # 按时间正序回滚（先扣的后回滚）
        batch_txs.reverse()
        for t in batch_txs:
            c = t["code"]
            d = t["delta"]
            inv.add(c, abs(d))
            new_balance = inv.get_quantity(c)
            inv_dao.add_transaction(
                code=c,
                delta=abs(d),
                balance=new_balance,
                tx_type="rollback",
                ref_id=ref_id,
                note="撤销制作消耗",
            )
            undone.append(c)
    else:
        # 单条撤销（add 或 remove）
        if tx_type == "add":
            inv.remove(code, delta)
            new_balance = inv.get_quantity(code)
            inv_dao.add_transaction(
                code=code,
                delta=-delta,
                balance=new_balance,
                tx_type="rollback",
                note="撤销添加",
            )
        elif tx_type in ("remove", "make_consume"):
            inv.add(code, abs(delta))
            new_balance = inv.get_quantity(code)
            inv_dao.add_transaction(
                code=code,
                delta=abs(delta),
                balance=new_balance,
                tx_type="rollback",
                note="撤销消耗",
            )
        undone.append(code)

    inv_dao.save_inventory(inv)
    return {"ok": True, "undone": undone}


def undo_make_by_record(record_id: int) -> dict:
    """按制作记录 ID 撤销制作消耗。

    Returns:
        {"ok": True, "undone": list}
        或 {"ok": False, "error": str}
    """
    make_dao = MakeRecordDao()
    record = make_dao.get(record_id)
    if not record:
        return {"ok": False, "error": "制作记录不存在"}
    if record.get("status") == "undone":
        return {"ok": False, "error": "该记录已撤销"}

    inv_dao = InventoryDao()
    inv = inv_dao.load_inventory()
    if not inv:
        return {"ok": False, "error": "库存未初始化"}

    # 找到该记录关联的全部 make_consume 事务
    batch_txs = inv_dao.list_transactions(limit=1000)
    batch_txs = [t for t in batch_txs if t.get("ref_id") == record_id and t["tx_type"] == "make_consume"]
    if not batch_txs:
        return {"ok": False, "error": "未找到关联的库存事务"}

    # 按时间正序回滚（先扣的后回滚）
    batch_txs.reverse()
    undone = []
    for t in batch_txs:
        c = t["code"]
        d = t["delta"]
        inv.add(c, abs(d))
        new_balance = inv.get_quantity(c)
        inv_dao.add_transaction(
            code=c,
            delta=abs(d),
            balance=new_balance,
            tx_type="rollback",
            ref_id=record_id,
            note="撤销制作消耗",
        )
        undone.append(c)

    inv_dao.save_inventory(inv)

    # 更新制作记录状态
    make_dao.update_status(record_id, "undone")

    return {"ok": True, "undone": undone}
