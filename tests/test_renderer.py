import datetime as dt

from pypdf import PdfReader

from signal_matin.mock_data import construire_demo
from signal_matin.models import DensityMode
from signal_matin.normalizer import normaliser_edition
from signal_matin.pdf import generer_pdf, inspecter_html
from signal_matin.renderer import render_html


EXPECTED_PAGES = {
    DensityMode.COMPACT: 4,
    DensityMode.STANDARD: 8,
    DensityMode.EXTENDED: 8,
}


def test_html_has_expected_pages_and_sections():
    demo = construire_demo(dt.date(2026, 9, 26))
    for mode, count in EXPECTED_PAGES.items():
        edition = normaliser_edition(demo, mode=mode)
        html = render_html(edition)
        assert html.count('class="sheet ') == count
        assert "Signal Matin" in html
        assert "En bref, en detail" in html


def test_no_major_overflow():
    demo = construire_demo(dt.date(2026, 9, 26))
    for mode, count in EXPECTED_PAGES.items():
        edition = normaliser_edition(demo, mode=mode)
        layout = inspecter_html(render_html(edition))
        assert len(layout) == count
        assert not [page for page in layout if page["overflow"]]


def test_pdf_is_a4(tmp_path):
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard")
    path = generer_pdf(edition, tmp_path / "signal-matin.pdf")
    reader = PdfReader(str(path))
    assert len(reader.pages) == EXPECTED_PAGES[DensityMode.STANDARD]
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.28) < 1.0
        assert abs(float(page.mediabox.height) - 841.89) < 1.0
