"""
Validation + extraction integration tests for Purchase Trace.

Test cases:
  1. Single valid grocery receipt   → passes validation, items[] populated
  2. 3 images of the same receipt   → passes same-document check, items[] populated
  3. 2 images of different receipts → rejected: is_single_document=False
  4. Non-purchase image (PNG badge) → rejected: is_valid_purchase_document=False
  5. Utility bill (electricity)     → passes validation, items[] empty,
                                       total_amount set, due_date extracted

Run with:
    cd backend
    .venv\\Scripts\\pytest app/tests/test_validation.py -v
Requires GEMINI_API_KEY to be set in backend/.env
"""

import io
import os
import sys
import textwrap
import pytest
import httpx
from PIL import Image, ImageDraw, ImageFont
from asgi_lifespan import LifespanManager
from httpx import ASGITransport

# ── make sure backend package is importable ────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from app.main import app  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE IMAGE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _text_to_jpeg(text: str, width: int = 640, filename: str = "out.jpg") -> bytes:
    """Render monospaced text onto a white JPEG and return bytes."""
    lines = text.strip().splitlines()
    line_h = 20
    padding = 20
    height = len(lines) * line_h + padding * 2
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("cour.ttf", 15)  # Courier on Windows
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((padding, padding + i * line_h), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    path = os.path.join(FIXTURES_DIR, filename)
    buf.seek(0)
    with open(path, "wb") as f:
        f.write(buf.read())
    buf.seek(0)
    return buf.read()


def _make_grocery_receipt() -> bytes:
    text = textwrap.dedent("""\
        FRESHMARKET GROCERY
        142 Main St  |  Tel: 555-1234
        --------------------------------
        Date: 07/10/2024  16:48
        Transaction #12345  Cashier: Sarah
        --------------------------------
        MILK, 1 GAL (WHOLE)         $3.79
        BREAD, SLICED WHEAT         $2.49
        APPLES, GALA (3 LB BAG)     $4.99
        CHEESE, CHEDDAR             $3.99
        --------------------------------
        SUBTOTAL                   $15.26
        TAX 8%                      $1.22
        TOTAL                      $16.48
        PAID: DEBIT
        --------------------------------
        HAVE A NICE DAY!
    """)
    return _text_to_jpeg(text, filename="receipt_single.jpg")


def _make_long_receipt_top() -> bytes:
    text = textwrap.dedent("""\
        SUPERMALL ELECTRONICS
        Plot 4, MG Road, Bengaluru
        GSTIN: 29ABCDE1234F1Z5
        --------------------------------
        Invoice #: INV-20240710-0088
        Date: 10-Jul-2024  Time: 14:22
        Cashier: Priya
        --------------------------------
        1. Samsung Galaxy S24      49999
        2. Phone Case (Clear)        799
        3. Tempered Glass            299
        >> continued on next photo >>
    """)
    return _text_to_jpeg(text, filename="receipt_long_top.jpg")


def _make_long_receipt_bottom() -> bytes:
    text = textwrap.dedent("""\
        >> continued from previous photo >>
        Invoice #: INV-20240710-0088
        --------------------------------
        4. USB-C Cable (2m)           499
        5. Wireless Earbuds          2999
        --------------------------------
        SUBTOTAL                   54595
        GST 18%                     9827
        TOTAL AMOUNT PAYABLE       64422
        PAID: UPI  Ref: 812345678
        --------------------------------
        Thank you for shopping with us!
    """)
    return _text_to_jpeg(text, filename="receipt_long_bottom.jpg")


def _make_long_receipt_middle() -> bytes:
    """Middle fragment of the same long receipt — just item rows."""
    text = textwrap.dedent("""\
        >> page 2 of 3 — Invoice #: INV-20240710-0088 <<
        --------------------------------
        (continued)
        3. Tempered Glass            299
        4. USB-C Cable (2m)          499
        --------------------------------
    """)
    return _text_to_jpeg(text, filename="receipt_long_middle.jpg")


def _make_different_receipt_a() -> bytes:
    text = textwrap.dedent("""\
        RESTAURANT A — PIZZA PALACE
        Order #1001  Date: 10-Jul-2024
        --------------------------------
        Margherita Pizza (M)        450
        Garlic Bread                150
        Coke 500ml                   80
        --------------------------------
        TOTAL                       680
        PAID: CASH
    """)
    return _text_to_jpeg(text, filename="receipt_diff_a.jpg")


def _make_different_receipt_b() -> bytes:
    text = textwrap.dedent("""\
        SUPERMART — DAILY GROCERY
        Bill No: 4421  Date: 08-Jul-2024
        --------------------------------
        Toor Dal 1kg                120
        Sunflower Oil 1L            180
        Sugar 1kg                    55
        --------------------------------
        TOTAL                       355
        PAID: UPI
    """)
    return _text_to_jpeg(text, filename="receipt_diff_b.jpg")


def _make_non_purchase_image() -> bytes:
    """A plain coloured rectangle — clearly not a receipt."""
    img = Image.new("RGB", (400, 300), color=(30, 144, 255))  # dodger-blue rectangle
    draw = ImageDraw.Draw(img)
    draw.text((80, 130), "HELLO WORLD", fill="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    path = os.path.join(FIXTURES_DIR, "non_purchase.jpg")
    buf.seek(0)
    with open(path, "wb") as f:
        f.write(buf.read())
    buf.seek(0)
    return buf.read()


def _make_electricity_bill() -> bytes:
    text = textwrap.dedent("""\
        TATA POWER — ELECTRICITY BILL
        Consumer No: 123456789
        Consumer Name: RAVI KUMAR
        Address: 12 Rose Garden, Mumbai - 400001
        ----------------------------------------
        Bill Date:        01-Aug-2024
        Bill Period:      Jul 2024
        Due Date:         20-Aug-2024
        ----------------------------------------
        MIN/ENERGY CHARGES           1,240.00
        FIXED CHARGES                  120.00
        CUSTOMER CHARGES                50.00
        ELECTRICITY DUTY (10%)         141.00
        FPPCA SURCHARGE                 28.50
        GOVERNMENT SUBSIDY             -200.00
        ADJUSTMENTS                      0.00
        ----------------------------------------
        NET AMOUNT PAYABLE           1,379.50
        ----------------------------------------
        If paid after 20-Aug-2024, late fee of Rs 50 applies.
        For queries: 1912 | www.tatapower.com
    """)
    return _text_to_jpeg(text, filename="electricity_bill.jpg")


# ═══════════════════════════════════════════════════════════════════════════
# PYTEST CLIENT FIXTURE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
async def client():
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=120.0,  # Gemini calls can be slow
        ) as c:
            yield c


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _upload_files(files_data: list[tuple[str, bytes, str]]):
    """
    files_data: list of (field_name, bytes, filename)
    Returns the multipart `files` kwarg for httpx.
    """
    return [("files", (name, data, mime)) for name, data, mime in files_data]


# ═══════════════════════════════════════════════════════════════════════════
# TEST CASES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_1_single_valid_grocery_receipt(client):
    """Single valid grocery receipt → validation passes, items[] populated."""
    img_bytes = _make_grocery_receipt()
    resp = await client.post(
        "/api/documents/upload",
        files=_upload_files([("receipt_single.jpg", img_bytes, "image/jpeg")]),
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    # Validation block
    val = data["validation"]
    assert val["is_valid_purchase_document"] is True
    assert val["is_single_document"] is True
    assert val["rejection_reason"] is None

    # Extraction block
    doc = data["document"]["extracted_data"]
    assert doc["merchant_name"]              # non-empty
    assert doc["total_amount"] > 0
    assert isinstance(doc["items"], list)
    assert len(doc["items"]) > 0, "Expected grocery items in items[]"


@pytest.mark.anyio
async def test_2_three_photos_same_receipt(client):
    """3 photos of the same long receipt → same-doc check passes, items[] merged."""
    top = _make_long_receipt_top()
    mid = _make_long_receipt_middle()
    bot = _make_long_receipt_bottom()
    resp = await client.post(
        "/api/documents/upload",
        files=_upload_files([
            ("receipt_long_top.jpg", top, "image/jpeg"),
            ("receipt_long_middle.jpg", mid, "image/jpeg"),
            ("receipt_long_bottom.jpg", bot, "image/jpeg"),
        ]),
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    val = data["validation"]
    assert val["is_valid_purchase_document"] is True
    assert val["is_single_document"] is True

    doc = data["document"]["extracted_data"]
    assert data["document"]["image_count"] == 3, f"Expected image_count=3, got {data['document']['image_count']}"
    assert doc["total_amount"] > 0
    assert len(doc["items"]) >= 3, "Expected at least 3 merged items across photos"


@pytest.mark.anyio
async def test_3_two_photos_different_receipts(client):
    """2 photos of clearly different receipts → 422 DIFFERENT_RECEIPTS."""
    a = _make_different_receipt_a()
    b = _make_different_receipt_b()
    resp = await client.post(
        "/api/documents/upload",
        files=_upload_files([
            ("receipt_diff_a.jpg", a, "image/jpeg"),
            ("receipt_diff_b.jpg", b, "image/jpeg"),
        ]),
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert detail["code"] == "DIFFERENT_RECEIPTS"
    assert detail["validation"]["is_single_document"] is False
    assert detail["message"]  # non-empty rejection reason


@pytest.mark.anyio
async def test_4_non_purchase_image_rejected(client):
    """A plain coloured image → 422 NOT_PURCHASE_DOCUMENT."""
    img_bytes = _make_non_purchase_image()
    resp = await client.post(
        "/api/documents/upload",
        files=_upload_files([("non_purchase.jpg", img_bytes, "image/jpeg")]),
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert detail["code"] == "NOT_PURCHASE_DOCUMENT"
    assert detail["validation"]["is_valid_purchase_document"] is False
    assert detail["message"]


@pytest.mark.anyio
async def test_5_utility_bill_empty_items_due_date(client):
    """
    Electricity bill → validation passes, items[] is empty [],
    total_amount matches net payable, due_date is distinct from purchase_date.
    """
    bill_bytes = _make_electricity_bill()
    resp = await client.post(
        "/api/documents/upload",
        files=_upload_files([("electricity_bill.jpg", bill_bytes, "image/jpeg")]),
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    val = data["validation"]
    assert val["is_valid_purchase_document"] is True, (
        "Electricity bill should be recognised as a valid purchase document"
    )

    doc = data["document"]["extracted_data"]

    # Core assertion: no billing components in items[]
    assert doc["items"] == [], (
        f"items[] must be empty for a utility bill, got: {doc['items']}"
    )

    # total_amount = net amount payable (1379.50)
    assert abs(doc["total_amount"] - 1379.50) < 1.0, (
        f"total_amount mismatch: {doc['total_amount']}"
    )

    # due_date present and different from purchase_date
    assert doc["due_date"] is not None, "due_date should be extracted from 'Due Date' line"
    assert doc["purchase_date"] is not None, "purchase_date (bill date) should be extracted"
    assert doc["due_date"] != doc["purchase_date"], (
        f"due_date ({doc['due_date']}) must differ from purchase_date ({doc['purchase_date']})"
    )
