import json
import sys
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

# 确保能导入 bead_matcher 包
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bead_matcher.color_chart import convert_code, get_chart, list_brands
from bead_matcher.dao.inventory_dao import InventoryDao
from bead_matcher.inventory import Inventory
from bead_matcher.pattern_converter import convert_image_to_pattern, postprocess_grid_colors, suggest_grid_size
from bead_matcher.pattern_storage import PatternLibrary
from bead_matcher.storage import load_inventory, save_inventory
from bead_matcher.thumbnail import generate_thumbnail, thumbnail_exists
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB


def _get_inventory(brand: str = "Mard"):
    return load_inventory(brand=brand)


def _get_chart_for(brand: str):
    return get_chart(brand)


@app.route("/")
def index():
    return render_template("inventory.html")


# ---------- 库存 API ----------

@app.route("/api/inventory")
def api_inventory():
    brand = request.args.get("brand", "Mard")
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"brand": None, "items": [], "total": 0})
    chart = _get_chart_for(inv.brand)
    items = []
    for code in inv.list_codes():
        color = chart.get(code) if chart else None
        items.append({
            "code": code,
            "name": color.name if color else "未知色号",
            "hex": color.hex_color if color else None,
            "quantity": inv.get_quantity(code),
        })
    invalid = inv.validate_against_chart() if chart else []
    return jsonify({
        "brand": inv.brand,
        "items": items,
        "total": inv.total_count(),
        "invalid": invalid,
    })


@app.route("/api/inventory/init", methods=["POST"])
def api_inventory_init():
    brand = request.json.get("brand", "Mard") if request.json else "Mard"
    inv = Inventory(brand=brand)
    save_inventory(inv)
    return jsonify({"ok": True, "brand": brand})


@app.route("/api/inventory/add", methods=["POST"])
def api_inventory_add():
    brand = request.json.get("brand", "Mard") if request.json else "Mard"
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"ok": False, "error": "尚未初始化库存"}), 400
    code = request.json.get("code", "").strip()
    qty = request.json.get("quantity", 0)
    try:
        inv.add(code, int(qty))
        save_inventory(inv)
        return jsonify({"ok": True, "quantity": inv.get_quantity(code)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/inventory/set", methods=["POST"])
def api_inventory_set():
    brand = request.json.get("brand", "Mard") if request.json else "Mard"
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"ok": False, "error": "尚未初始化库存"}), 400
    code = request.json.get("code", "").strip()
    qty = request.json.get("quantity", 0)
    try:
        inv.set(code, int(qty))
        save_inventory(inv)
        return jsonify({"ok": True, "quantity": inv.get_quantity(code)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/inventory/remove", methods=["POST"])
def api_inventory_remove():
    brand = request.json.get("brand", "Mard") if request.json else "Mard"
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"ok": False, "error": "尚未初始化库存"}), 400
    code = request.json.get("code", "").strip()
    qty = request.json.get("quantity", 0)
    try:
        inv.remove(code, int(qty))
        save_inventory(inv)
        return jsonify({"ok": True, "quantity": inv.get_quantity(code)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/inventory/clear", methods=["POST"])
def api_inventory_clear():
    brand = request.json.get("brand", "Mard") if request.json else "Mard"
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"ok": False, "error": "库存未初始化"}), 400
    inv.items.clear()
    save_inventory(inv)
    return jsonify({"ok": True})


@app.route("/api/inventory/batch-init", methods=["POST"])
def api_inventory_batch_init():
    """批量初始化库存：清空后按传入列表设置。（品牌默认 Mard，后端已预留扩展）"""
    items = request.json.get("items", [])
    brand = request.json.get("brand", "Mard")
    inv = Inventory(brand=brand)
    for item in items:
        code = item.get("code", "").strip()
        qty = item.get("quantity", 0)
        if code and qty > 0:
            inv.set(code, qty)
    save_inventory(inv)

    dao = InventoryDao()
    for item in items:
        code = item.get("code", "").strip()
        qty = item.get("quantity", 0)
        if code and qty > 0:
            dao.add_transaction(code, qty, qty, "init", note="初始化库存")

    return jsonify({"ok": True, "colors": len(inv.items), "total": inv.total_count()})


@app.route("/api/inventory/batch-add", methods=["POST"])
def api_inventory_batch_add():
    """批量补货：在现有库存上累加。"""
    brand = request.json.get("brand", "Mard") if request.json else "Mard"
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"ok": False, "error": "尚未初始化库存"}), 400

    items = request.json.get("items", [])
    for item in items:
        code = item.get("code", "").strip()
        qty = item.get("quantity", 0)
        if code and qty > 0:
            inv.add(code, qty)
    save_inventory(inv)

    dao = InventoryDao()
    for item in items:
        code = item.get("code", "").strip()
        qty = item.get("quantity", 0)
        if code and qty > 0:
            balance = inv.get_quantity(code)
            dao.add_transaction(code, qty, balance, "add", note="补货录入")

    return jsonify({"ok": True, "colors": len(inv.items), "total": inv.total_count()})


# ---------- 色号转换 API ----------

@app.route("/api/convert-code")
def api_convert_code():
    """跨品牌色号转换：?from=Mard&to=Coco&code=A01"""
    from_brand = request.args.get("from", "Mard")
    to_brand = request.args.get("to", "")
    code = request.args.get("code", "").strip()
    if not to_brand or not code:
        return jsonify({"ok": False, "error": "缺少 to 或 code 参数"}), 400
    result = convert_code(from_brand, to_brand, code)
    if result:
        return jsonify({"ok": True, "from": from_brand, "to": to_brand, "from_code": code, "to_code": result})
    return jsonify({"ok": False, "error": f"未找到 {from_brand} {code} 在 {to_brand} 中的对应色号"}), 404


# ---------- 色卡 API ----------

@app.route("/api/chart/<brand>")
def api_chart(brand):
    chart = _get_chart_for(brand)
    if not chart:
        return jsonify({"ok": False, "error": "未知品牌"}), 404
    colors = []
    for code in chart.list_codes():
        c = chart.get(code)
        colors.append({"code": c.code, "name": c.name, "hex": c.hex_color})
    return jsonify({"brand": brand, "colors": colors})


@app.route("/api/brands")
def api_brands():
    return jsonify(list_brands())


# ---------- 图案库 API ----------

@app.route("/api/patterns")
def api_patterns():
    lib = PatternLibrary()
    patterns = lib.list_all()

    # 查询参数
    search = request.args.get("search", "").strip().lower()
    brand = request.args.get("brand", "").strip()
    status = request.args.get("status", "").strip()
    ip = request.args.get("ip", "").strip()

    if search:
        patterns = [p for p in patterns if search in p.name.lower()]
    if brand:
        patterns = [p for p in patterns if p.brand == brand]
    if status:
        patterns = [p for p in patterns if p.status == status]
    if ip:
        patterns = [p for p in patterns if ip in p.ip_name]

    result = []
    for p in patterns:
        result.append({
            "id": p.id,
            "name": p.name,
            "brand": p.brand,
            "width": p.width,
            "height": p.height,
            "total_beads": p.total_beads(),
            "colors": len(p.color_usage),
            "input_mode": p.input_mode,
            "source_image": p.source_image,
            "status": p.status,
            "ip_name": p.ip_name,
        })
    return jsonify(result)


@app.route("/api/patterns/<pattern_id>")
def api_pattern_detail(pattern_id):
    lib = PatternLibrary()
    p = lib.get_by_id(pattern_id)
    if not p:
        return jsonify({"ok": False, "error": "图案不存在"}), 404
    chart = _get_chart_for(p.brand)
    color_details = []
    for code in p.unique_colors():
        color = chart.get(code) if chart else None
        color_details.append({
            "code": code,
            "name": color.name if color else "未知",
            "hex": color.hex_color if color else None,
            "count": p.color_usage.get(code, 0),
        })
    return jsonify({
        "id": p.id,
        "name": p.name,
        "brand": p.brand,
        "width": p.width,
        "height": p.height,
        "total_beads": p.total_beads(),
        "input_mode": p.input_mode,
        "source_image": p.source_image,
        "status": p.status,
        "ip_name": p.ip_name,
        "color_usage": color_details,
        "grid": {f"{c},{r}": code for (c, r), code in p.grid.items()} if p.grid else {},
    })


@app.route("/api/patterns/<pattern_id>", methods=["PUT"])
def api_pattern_update(pattern_id):
    lib = PatternLibrary()
    p = lib.get_by_id(pattern_id)
    if not p:
        return jsonify({"ok": False, "error": "图案不存在"}), 404

    data = request.json or {}

    # 更新基本字段
    if "name" in data:
        p.name = data["name"].strip() or p.name
    if "ip_name" in data:
        raw = data["ip_name"]
        if isinstance(raw, list):
            p.ip_name = [x.strip() for x in raw if x and x.strip()]
        elif isinstance(raw, str):
            p.ip_name = [raw.strip()] if raw.strip() else []
        else:
            p.ip_name = []
    if "width" in data:
        p.width = max(1, int(data["width"]))
    if "height" in data:
        p.height = max(1, int(data["height"]))
    if "status" in data:
        p.status = data["status"] if data["status"] in ("pending", "done") else p.status

    # 更新色号用量
    if "color_usage" in data:
        new_usage = {}
        for code, qty in data["color_usage"].items():
            code = str(code).strip()
            if code and int(qty) > 0:
                new_usage[code] = int(qty)
        if new_usage:
            old_keys = set(p.color_usage.keys())
            new_keys = set(new_usage.keys())
            p.color_usage = new_usage
            # 如果色号集合变了，grid 无法同步，清空降级为 manual_entry
            if old_keys != new_keys:
                p.grid = {}
                p.input_mode = "manual_entry"

    # 保存更新
    from bead_matcher.dao.pattern_dao import PatternDao
    PatternDao().save(p)

    chart = _get_chart_for(p.brand)
    color_details = []
    for code in p.unique_colors():
        color = chart.get(code) if chart else None
        color_details.append({
            "code": code,
            "name": color.name if color else "未知",
            "hex": color.hex_color if color else None,
            "count": p.color_usage.get(code, 0),
        })
    return jsonify({
        "ok": True,
        "pattern": {
            "id": p.id,
            "name": p.name,
            "brand": p.brand,
            "width": p.width,
            "height": p.height,
            "total_beads": p.total_beads(),
            "input_mode": p.input_mode,
            "source_image": p.source_image,
            "status": p.status,
            "ip_name": p.ip_name,
            "color_usage": color_details,
        },
    })


@app.route("/api/patterns/<pattern_id>", methods=["DELETE"])
def api_pattern_delete(pattern_id):
    lib = PatternLibrary()
    if lib.remove_by_id(pattern_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "图案不存在"}), 404


@app.route("/api/patterns/<pattern_id>/make", methods=["POST"])
def api_pattern_make(pattern_id):
    """制作图案：扣除库存并记录制作历史。"""
    data = request.json or {}
    copies = int(data.get("copies", 1))
    if copies < 1:
        return jsonify({"ok": False, "error": "份数至少为 1"}), 400

    lib = PatternLibrary()
    pattern = lib.get_by_id(pattern_id)
    if not pattern:
        return jsonify({"ok": False, "error": "图案不存在"}), 404

    from bead_matcher.inventory_service import make_pattern
    result = make_pattern(pattern, copies=copies)
    return jsonify(result)


@app.route("/api/patterns/<pattern_id>/makes")
def api_pattern_makes(pattern_id):
    """返回指定图案的制作历史。"""
    from bead_matcher.dao.make_record_dao import MakeRecordDao
    dao = MakeRecordDao()
    records = dao.list_by_pattern(pattern_id)
    return jsonify(records)


@app.route("/api/makes/<int:record_id>/undo", methods=["POST"])
def api_undo_make(record_id):
    """撤销指定制作记录。"""
    from bead_matcher.inventory_service import undo_make_by_record
    result = undo_make_by_record(record_id)
    return jsonify(result)


# ---------- 格子图 PNG 生成 ----------

def _get_grid_font(size: int):
    """加载适合绘制格子文字的字体。"""
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _is_light_color(hex_color: str) -> bool:
    if not hex_color or len(hex_color) < 7:
        return True
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return (r * 299 + g * 587 + b * 114) / 1000 > 128


@app.route("/api/patterns/<pattern_id>/grid.png")
def api_pattern_grid_image(pattern_id):
    """生成带格线和色号标注的拼豆网格 PNG。"""
    lib = PatternLibrary()
    p = lib.get_by_id(pattern_id)
    if not p or not p.grid:
        return jsonify({"ok": False, "error": "图案不存在或无网格数据"}), 404

    cell_size = request.args.get("cell_size", 24, type=int)
    show_code = request.args.get("show_code", 1, type=int)
    gap = 1

    chart = _get_chart_for(p.brand)
    color_map = {}
    for code in p.unique_colors():
        color = chart.get(code) if chart else None
        color_map[code] = color.hex_color if color else "#cccccc"

    # 色卡数据
    sorted_colors = sorted(
        p.color_usage.items(), key=lambda x: -x[1]
    )

    # 图片尺寸计算
    grid_w = p.width * cell_size + (p.width + 1) * gap
    grid_h = p.height * cell_size + (p.height + 1) * gap

    legend_margin = 20
    legend_title_h = 30
    legend_row_h = 28
    legend_padding = 16
    legend_h = legend_title_h + len(sorted_colors) * legend_row_h + legend_padding * 2

    img_w = max(grid_w, 320)
    img_h = grid_h + legend_margin + legend_h

    img = Image.new("RGB", (img_w, img_h), "#ffffff")
    draw = ImageDraw.Draw(img)

    font_size = max(8, cell_size // 3)
    font = _get_grid_font(font_size)
    legend_font = _get_grid_font(13)
    title_font = _get_grid_font(15)

    # 绘制 grid（居中）
    grid_offset_x = (img_w - grid_w) // 2
    for row in range(p.height):
        for col in range(p.width):
            code = p.grid.get((col, row))
            hex_color = color_map.get(code, "#cccccc")

            x = grid_offset_x + col * (cell_size + gap) + gap
            y = row * (cell_size + gap) + gap

            draw.rectangle(
                [x, y, x + cell_size - 1, y + cell_size - 1],
                fill=hex_color,
            )

            if show_code and code and cell_size >= 16:
                text_color = "#333333" if _is_light_color(hex_color) else "#ffffff"
                bbox = draw.textbbox((0, 0), code, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                text_x = x + (cell_size - text_w) // 2
                text_y = y + (cell_size - text_h) // 2
                draw.text((text_x, text_y), code, fill=text_color, font=font)

    # 绘制色卡区域
    legend_y = grid_h + legend_margin
    # 分隔线
    draw.line([(16, legend_y - 8), (img_w - 16, legend_y - 8)], fill="#dddddd", width=1)
    # 标题
    draw.text((20, legend_y), "色卡对照表", fill="#333333", font=title_font)
    legend_y += legend_title_h

    for code, count in sorted_colors:
        color = chart.get(code) if chart else None
        hex_color = color.hex_color if color else "#cccccc"
        name = color.name if color else "未知"

        # 色块
        draw.rectangle([20, legend_y + 4, 44, legend_y + 24], fill=hex_color, outline="#999999", width=1)
        # 文字
        text = f"{code}    {name}    {count} 粒"
        draw.text((54, legend_y + 4), text, fill="#333333", font=legend_font)

        legend_y += legend_row_h

    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---------- 手动录入图案 API ----------

@app.route("/api/patterns/manual", methods=["POST"])
def api_pattern_manual():
    """手动录入已有拼豆图案（非图片转换）。"""
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "图案名称不能为空"}), 400

    color_usage = data.get("color_usage", {})
    if not color_usage:
        return jsonify({"ok": False, "error": "至少需要一个色号及数量"}), 400

    brand = data.get("brand", "Mard").strip()
    width = data.get("width", 0)
    height = data.get("height", 0)
    ip_name = data.get("ip_name") or []
    if isinstance(ip_name, str):
        ip_name = [ip_name] if ip_name.strip() else []
    status = data.get("status", "pending")
    tags = data.get("tags", [])

    lib = PatternLibrary()
    pattern = lib.create_manual(
        name=name,
        color_usage=color_usage,
        brand=brand,
        width=width,
        height=height,
        ip_name=ip_name,
        status=status,
        tags=tags,
    )
    return jsonify({
        "ok": True,
        "pattern": {
            "id": pattern.id,
            "name": pattern.name,
            "brand": pattern.brand,
            "width": pattern.width,
            "height": pattern.height,
            "total_beads": pattern.total_beads(),
            "colors": len(pattern.color_usage),
            "status": pattern.status,
            "ip_name": pattern.ip_name,
        },
    })


@app.route("/api/patterns/<pattern_id>/thumbnail", methods=["POST"])
def api_pattern_thumbnail(pattern_id):
    """为指定图案上传缩略图并保存原始大图。"""
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "未上传图片"}), 400
    file = request.files["image"]
    upload_dir = PROJECT_ROOT / "uploads"
    upload_dir.mkdir(exist_ok=True)
    temp_path = upload_dir / file.filename
    file.save(temp_path)
    try:
        # 保存原始大图
        images_dir = PROJECT_ROOT / "data" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        from PIL import Image as PILImage
        img = PILImage.open(temp_path)
        img.save(images_dir / f"{pattern_id}.png", "PNG")
        # 生成缩略图
        generate_thumbnail(temp_path, pattern_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/thumbnails/<pattern_id>.png")
def serve_thumbnail(pattern_id):
    """服务缩略图文件。"""
    thumb_dir = PROJECT_ROOT / "data" / "thumbnails"
    if not thumb_dir.exists():
        return jsonify({"ok": False, "error": "缩略图不存在"}), 404
    return send_from_directory(thumb_dir, f"{pattern_id}.png")


@app.route("/images/<pattern_id>.png")
def serve_image(pattern_id):
    """服务原始大图文件。"""
    images_dir = PROJECT_ROOT / "data" / "images"
    if not images_dir.exists():
        return jsonify({"ok": False, "error": "图片不存在"}), 404
    return send_from_directory(images_dir, f"{pattern_id}.png")


@app.route("/api/pattern-ips")
def api_pattern_ips():
    """返回所有已存在的 IP / 来源名称（标签库 + 已保存图案聚合）。"""
    lib = PatternLibrary()
    ips = set(lib.list_ip_tags())  # 从独立标签库读取
    for p in lib.list_all():       # 兼容：也从已保存图案聚合
        for ip in p.ip_name:
            if ip:
                ips.add(ip)
    return jsonify(sorted(ips))


@app.route("/api/pattern-ips", methods=["POST"])
def api_add_ip_tag():
    """注册新 IP 标签到标签库。"""
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "标签名称不能为空"}), 400
    lib = PatternLibrary()
    added = lib.add_ip_tag(name)
    return jsonify({"ok": True, "added": added})


@app.route("/api/pattern-ips/<name>", methods=["DELETE"])
def api_remove_ip_tag(name):
    """从标签库删除 IP 标签（不影响已关联图案的字段）。"""
    lib = PatternLibrary()
    removed = lib.remove_ip_tag(name)
    return jsonify({"ok": removed})


# ---------- 图片转换 API ----------

@app.route("/api/convert", methods=["POST"])
def api_convert():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "未上传图片"}), 400

    file = request.files["image"]
    brand = request.form.get("brand", "Mard")
    name = request.form.get("name", "").strip()
    width = request.form.get("width", "").strip()
    height = request.form.get("height", "").strip()

    if not name:
        return jsonify({"ok": False, "error": "图案名称不能为空"}), 400

    # 保存上传图片到临时目录
    upload_dir = PROJECT_ROOT / "uploads"
    upload_dir.mkdir(exist_ok=True)
    image_path = upload_dir / file.filename
    file.save(image_path)

    try:
        target_w = int(width) if width else None
        target_h = int(height) if height else None

        if target_w is None or target_h is None:
            suggested_w, suggested_h = suggest_grid_size(image_path)
            if target_w is None:
                target_w = suggested_w
            if target_h is None:
                target_h = suggested_h

        max_colors = int(request.form.get("max_colors", 20) or 20)
        threshold = float(request.form.get("threshold", 0) or 0)

        pattern = convert_image_to_pattern(
            image_path=image_path,
            brand=brand,
            target_width=target_w,
            target_height=target_h,
            name=name,
            source_image=str(file.filename),
        )

        # 颜色后处理：限制颜色数 + 合并相似色
        if threshold > 0 or len(pattern.color_usage) > max_colors:
            chart = _get_chart_for(pattern.brand)
            if chart:
                new_grid = postprocess_grid_colors(
                    pattern.grid,
                    pattern.color_usage,
                    chart,
                    max_colors=max_colors,
                    threshold=threshold,
                )
                pattern.grid = new_grid
                pattern._rebuild_usage()

        lib = PatternLibrary()
        lib.add(pattern)

        # 保存原始大图和缩略图
        try:
            images_dir = PROJECT_ROOT / "data" / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            from PIL import Image as PILImage
            img = PILImage.open(image_path)
            img.save(images_dir / f"{pattern.id}.png", "PNG")
            generate_thumbnail(image_path, pattern.id)
        except Exception as e:
            app.logger.warning(f"缩略图生成失败: {e}")

        chart = _get_chart_for(pattern.brand)
        color_details = []
        for code, count in pattern.color_usage.items():
            color = chart.get(code) if chart else None
            color_details.append({
                "code": code,
                "name": color.name if color else "未知",
                "hex": color.hex_color if color else None,
                "count": count,
            })

        return jsonify({
            "ok": True,
            "pattern": {
                "id": pattern.id,
                "name": pattern.name,
                "brand": pattern.brand,
                "width": pattern.width,
                "height": pattern.height,
                "total_beads": pattern.total_beads(),
                "colors": len(pattern.color_usage),
                "grid": {f"{c},{r}": code for (c, r), code in pattern.grid.items()},
                "color_usage": color_details,
            },
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# ---------- 库存匹配 API ----------

@app.route("/api/match")
def api_match():
    brand = request.args.get("brand", "Mard")
    inv = _get_inventory(brand)
    if not inv:
        return jsonify({"ok": False, "error": "尚未初始化库存"}), 400

    lib = PatternLibrary()
    inventory_qty = {code: inv.get_quantity(code) for code in inv.list_codes()}

    fully = []
    for p in lib.find_matching_patterns(inventory_qty):
        fully.append({
            "name": p.name,
            "brand": p.brand,
            "width": p.width,
            "height": p.height,
            "total_beads": p.total_beads(),
            "colors": len(p.color_usage),
        })

    partial = []
    for p, shortage in lib.find_partially_matching_patterns(inventory_qty):
        if shortage:
            partial.append({
                "name": p.name,
                "brand": p.brand,
                "width": p.width,
                "height": p.height,
                "total_beads": p.total_beads(),
                "shortage": shortage,
                "missing_total": sum(shortage.values()),
            })

    return jsonify({
        "inventory_brand": inv.brand,
        "inventory_total": inv.total_count(),
        "fully_match": fully,
        "partial_match": partial,
    })


# ---------- 页面路由 ----------

@app.route("/inventory")
def page_inventory():
    return render_template("inventory.html")


@app.route("/chart")
def page_chart():
    return render_template("chart.html")


@app.route("/convert")
def page_convert():
    return render_template("convert.html")


@app.route("/patterns")
def page_patterns():
    return render_template("patterns.html")


@app.route("/match")
def page_match():
    return render_template("match.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
