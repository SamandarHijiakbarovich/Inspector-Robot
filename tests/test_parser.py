import unittest
from pathlib import Path

from inspektor_bot.parsing import parse_report
from inspektor_bot.parsing.normalize import format_amount, normalize, parse_amount, parse_label_amount
from inspektor_bot.validator.models import ReportMeta

SAMPLE = (Path(__file__).parent / "fixtures" / "report_685_sample.txt").read_text(encoding="utf-8")


class NormalizeTests(unittest.TestCase):
    def test_apostrophes(self):
        self.assertEqual(normalize("Koʻrish  va  Ko‘rish"), "Ko'rish va Ko'rish")

    def test_parse_amount(self):
        self.assertEqual(parse_amount("234.2 mln so'm"), (234.2, "mln so'm"))
        self.assertEqual(parse_amount("0"), (0.0, None))
        self.assertEqual(parse_amount("1 234,5 mln so'm"), (1234.5, "mln so'm"))
        self.assertIsNone(parse_amount("2025 yil boshiga"))
        self.assertIsNone(parse_amount("2025-yildagi jami aylanmangizni kiriting"))

    def test_label_amount(self):
        self.assertEqual(
            parse_label_amount("• Soliqlar, yig'imlar — 187.5 mln so'm"),
            ("Soliqlar, yig'imlar", 187.5, "mln so'm"),
        )

    def test_format(self):
        self.assertEqual(format_amount(2.0), "2")
        self.assertEqual(format_amount(1234.56), "1 234.6")


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.report = parse_report(SAMPLE, ReportMeta(form_type="685"))

    def test_sections(self):
        self.assertEqual([s.number for s in self.report.sections], [1, 2, 3, 4, 5])
        self.assertEqual(self.report.sections[2].title, "Daromadlar")

    def test_codes(self):
        for code in ("2.1", "2.3", "3.1", "3.1a", "3.1e", "3.2", "4.1", "4.4", "5.4"):
            self.assertIn(code, self.report.items)

    def test_values(self):
        r = self.report
        self.assertEqual(r.amount("3.1"), 234.2)
        self.assertEqual(r.amount("3.1a"), 234.2)
        self.assertEqual(r.amount("2.1"), 222.8)
        self.assertEqual(r.amount("2.2"), 222.8)  # "Jami" qatori
        self.assertEqual(r.item("4.1").period("boshiga"), 267.7)
        self.assertEqual(r.item("4.1").period("oxiriga"), 370.1)
        self.assertEqual(r.item("3.2").texts, ["Mavjud emas"])
        self.assertEqual(len(r.item("2.2").values), 5)

    def test_footer_and_phone(self):
        r = self.report
        self.assertEqual(r.meta.status, "Yangi")
        self.assertEqual(r.meta.inn, "300383513")
        self.assertEqual(r.phone, "+998 99 500 47 77")
        self.assertEqual(r.item("5.4").texts, ["Yo'q, foydalanilmaydi"])

    def test_real_report(self):
        """inspektor.stat.uz dan robot o'qigan haqiqiy hisobot matni (telefon yashirilgan)."""
        text = (Path(__file__).parent / "fixtures" / "report_685_real_zero.txt").read_text(encoding="utf-8")
        r = parse_report(text)
        self.assertEqual([s.number for s in r.sections], [1, 2, 3, 4, 5])
        self.assertEqual(r.sections[1].title, "Xarajatlar va investitsiyalar")
        self.assertEqual(r.item("1.1").texts, ["01491", "Ipak qurtini ko'paytirish"])
        self.assertEqual(r.item("1.1").values, [])
        self.assertEqual(r.amount("1.4"), 0)
        self.assertEqual(r.item("1.4").values[0].unit, "%")
        self.assertEqual(r.amount("2.1"), 0)
        self.assertEqual(r.amount("3.1"), 0)
        self.assertEqual(r.item("4.4").period("oxiriga"), 0)
        self.assertEqual(r.item("5.2").texts, ["Foydalanilmaydi"])
        self.assertEqual(r.meta.status, "Yangi")
        self.assertEqual(r.meta.inn, "305832646")
        self.assertEqual(r.phone, "+998 90 000 00 00")

    def test_inline_layout(self):
        text = "3 Daromadlar\n3.1 2025-yildagi jami aylanmangizni kiriting\n10 mln so'm\n3.1a Qishloq xo'jaligi daromadlari\n10 mln so'm"
        r = parse_report(text)
        self.assertEqual(r.amount("3.1"), 10)
        self.assertEqual(r.amount("3.1a"), 10)

    def test_jarayonda_footer(self):
        text = SAMPLE.replace("Yangi\nSTIR", "Jarayonda\nTo'xtashev To'ychibek\nSTIR")
        r = parse_report(text)
        self.assertEqual(r.meta.status, "Jarayonda")
        self.assertEqual(r.meta.assigned_inspector, "To'xtashev To'ychibek")


if __name__ == "__main__":
    unittest.main()
