import unittest
from pathlib import Path

from inspektor_bot.parsing import parse_report
from inspektor_bot.validator import Decision, Severity, validate
from inspektor_bot.validator.comment_generator import REJECT_HEADER, build_comment
from inspektor_bot.validator.models import Finding, ReportMeta

SAMPLE = (Path(__file__).parent / "fixtures" / "report_685_sample.txt").read_text(encoding="utf-8")
SITE_WARNING = (
    "Yer va binolar ijarasi hamda elektr energiyasi, gaz, suv va boshqa kommunal xizmatlar uchun "
    "xarajatlar ko'rsatilmagan. Ma'lumotlarga aniqlik kiriting.\nIzoh: Ma'lumotlar togri korsatildi\n"
)
CLEAN = SAMPLE.replace(SITE_WARNING, "")


def check(text: str, opf: str = "130 Fermer xo'jaligi"):
    return validate(parse_report(text, ReportMeta(form_type="685", opf=opf)))


def rule_ids(result):
    return {f.rule_id for f in result.findings}


class DecisionTests(unittest.TestCase):
    def test_clean_report_accepted(self):
        result = check(CLEAN)
        self.assertEqual(result.findings, [])
        self.assertEqual(result.decision, Decision.ACCEPT)
        self.assertEqual(result.comment, "Tizim tomonidan avtomatik tekshirildi va qabul qilindi.")

    def test_site_warning_goes_to_manual(self):
        result = check(SAMPLE)
        self.assertEqual(rule_ids(result), {"SITE_WARNING"})
        self.assertEqual(result.decision, Decision.MANUAL)
        self.assertIn("togri korsatildi", result.comment)

    def test_children_sum_mismatch_rejected(self):
        text = CLEAN.replace(
            "o'rmon xo'jaligi va boshqalar)\n234.2 mln so'm", "o'rmon xo'jaligi va boshqalar)\n200 mln so'm")
        result = check(text)
        self.assertIn("CHILDREN_SUM_MISMATCH", rule_ids(result))
        self.assertEqual(result.decision, Decision.REJECT)
        self.assertTrue(result.comment.startswith(REJECT_HEADER))
        self.assertIn("3.1-satrdagi yakuniy summa (234.2 mln so'm) 3.1a–3.1e", result.comment)
        self.assertIn("farq 34.2 mln so'm", result.comment)

    def test_total_mismatch_rejected(self):
        result = check(CLEAN.replace("Jami\n222.8 mln so'm", "Jami\n250 mln so'm"))
        self.assertIn("TOTAL_MISMATCH", rule_ids(result))
        self.assertEqual(result.decision, Decision.REJECT)

    def test_expense_total_vs_breakdown(self):
        result = check(CLEAN.replace("kiriting.\n222.8\nmln so'm", "kiriting.\n240\nmln so'm"))
        self.assertEqual(rule_ids(result), {"EXPENSE_TOTAL_MISMATCH"})
        self.assertEqual(result.decision, Decision.REJECT)
        self.assertIn("2.1-savoldagi jami xarajatlar (240 mln so'm)", result.comment)

    def test_rounding_tolerated(self):
        result = check(CLEAN.replace("Jami\n222.8 mln so'm", "Jami\n222.9 mln so'm"))
        self.assertNotIn("TOTAL_MISMATCH", rule_ids(result))

    def test_empty_required_rejected(self):
        text = CLEAN.replace("tovarlar zaxiralari qiymati\n0\n2025 yil boshiga\n0\n2025 yil oxiriga\n",
                             "tovarlar zaxiralari qiymati\n")
        result = check(text)
        self.assertIn("REQUIRED_EMPTY", rule_ids(result))
        self.assertEqual(result.decision, Decision.REJECT)

    def test_stock_half_filled(self):
        text = CLEAN.replace("267.7\n2025 yil boshiga\n370.1\n2025 yil oxiriga", "267.7\n2025 yil boshiga")
        self.assertIn("STOCK_INCOMPLETE", rule_ids(check(text)))

    def test_missing_item_is_internal_manual(self):
        # Savol umuman topilmasa - korxona aybi emas, inspektor ko'rishi kerak
        text = CLEAN.replace("2.3\n2025 yilda kiritilgan", "2025 yilda kiritilgan")
        result = check(text)
        self.assertEqual(result.decision, Decision.MANUAL)
        self.assertTrue(any(f.internal for f in result.findings))

    def test_farm_without_agri_warning(self):
        text = CLEAN.replace("o'rmon xo'jaligi va boshqalar)\n234.2", "o'rmon xo'jaligi va boshqalar)\n0").replace(
            "o'zgartirmasdan sotish)\n0", "o'zgartirmasdan sotish)\n234.2")
        result = check(text)
        self.assertEqual(rule_ids(result), {"FARM_NO_AGRI"})
        self.assertEqual(result.decision, Decision.MANUAL)
        self.assertEqual(check(text, opf="110 Tijorat").decision, Decision.ACCEPT)

    def test_real_zero_report(self):
        text = (Path(__file__).parent / "fixtures" / "report_685_real_zero.txt").read_text(encoding="utf-8")
        result = check(text, opf="152 Tijorat tashkilotlari")
        self.assertEqual(rule_ids(result), {"ZERO_ACTIVITY"})  # 3.1a–3.1e endi talab qilinmaydi
        self.assertEqual(result.decision, Decision.MANUAL)
        self.assertIn("faoliyati bo'yicha ma'lumotlar ko'rsatilmagan", result.comment)

    def test_revenue_without_breakdown_is_internal(self):
        # 3.1 > 0, lakin 3.1a–3.1e satrlari umuman yo'q (parser yoki forma o'zgargan)
        start, end = CLEAN.index("3.1a\n"), CLEAN.index("3.2\n")
        result = check(CLEAN[:start] + CLEAN[end:])
        self.assertTrue(any(f.rule_id == "ITEM_NOT_FOUND" and f.code == "3.1a" for f in result.findings))
        self.assertEqual(result.decision, Decision.MANUAL)

    def test_unparseable_text_never_rejects(self):
        result = check("Server xatosi. Keyinroq urinib ko'ring.")
        self.assertEqual(result.decision, Decision.MANUAL)
        self.assertEqual(result.comment, "")


STOCK_WARNING = (
    "Tayyor mahsulot qoldig'i bir davrda 0, boshqa davrda esa musbat qiymatda ko'rsatilgan. "
    "Ma'lumotni tekshiring.\nIzoh: киритилган маълумотлар тугри\n"
)
WITH_STOCK_WARNING = CLEAN.replace(
    "qo'shgan holda)\n0\n2025 yil boshiga\n0\n2025 yil oxiriga\n",
    "qo'shgan holda)\n3.3\n2025 yil boshiga\n0\n2025 yil oxiriga\n" + STOCK_WARNING,
)


class SiteWarningTests(unittest.TestCase):
    def test_tekshiring_warning_detected(self):
        # Skrinshotdagi 4.4 ogohlantirishi: "...Ma'lumotni tekshiring." + Izoh
        self.assertNotEqual(WITH_STOCK_WARNING, CLEAN)
        result = check(WITH_STOCK_WARNING)
        self.assertEqual(rule_ids(result), {"SITE_WARNING"})
        self.assertEqual(result.findings[0].code, "4.4")
        self.assertEqual(result.decision, Decision.MANUAL)

    def test_reject_policy_comment_format(self):
        result = validate(parse_report(WITH_STOCK_WARNING, ReportMeta(form_type="685", opf="130")),
                          site_warning_action="reject")
        self.assertEqual(result.decision, Decision.REJECT)
        c = result.comment
        self.assertTrue(c.startswith(REJECT_HEADER))
        self.assertIn("1. 4.4. Tayyor mahsulot qoldig'i qiymati", c)
        self.assertIn("   • 2025 yil boshiga: 3.3", c)
        self.assertIn("   • 2025 yil oxiriga: 0", c)
        self.assertIn("   ⚠ Tayyor mahsulot qoldig'i bir davrda 0", c)
        self.assertIn("Respondent izohi: «киритилган маълумотлар тугри»", c)
        self.assertTrue(c.endswith("qayta topshiring."))

    def test_mismatch_comment_shows_question_and_values(self):
        text = CLEAN.replace(
            "o'rmon xo'jaligi va boshqalar)\n234.2 mln so'm", "o'rmon xo'jaligi va boshqalar)\n200 mln so'm")
        c = check(text).comment
        self.assertIn("1. 3.1. 2025-yildagi jami aylanmangizni kiriting", c)
        self.assertIn("   • 234.2 mln so'm", c)
        self.assertIn("   ⚠ 3.1-satrdagi yakuniy summa", c)


class SiteCheckTests(unittest.TestCase):
    def test_site_check_text(self):
        from inspektor_bot.validator.site_check import site_check_warnings
        text = (
            "• Soliqlar, yig'imlar va boshqa majburiy to'lovlar — 187.5 mln so'm\n"
            "• Jami — 222.8 mln so'm\n"
            "⚠ Yer va binolar ijarasi hamda kommunal xizmatlar uchun xarajatlar ko'rsatilmagan. "
            "Ma'lumotlarga aniqlik kiriting.\n"
            "Izoh: Ma'lumotlar togri korsatildi"
        )
        warnings = site_check_warnings(text)
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith("Yer va binolar"))
        self.assertEqual(site_check_warnings("• Jami — 10 mln so'm"), [])


class CommentTests(unittest.TestCase):
    def test_truncation(self):
        findings = [
            Finding("REQUIRED_EMPTY", Severity.ERROR, f"9.{i}", {"question": "x" * 60})
            for i in range(40)
        ]
        comment = build_comment(Decision.REJECT, findings, max_len=500)
        self.assertLessEqual(len(comment), 500)
        self.assertIn("ta nomuvofiqlik", comment)
        self.assertTrue(comment.endswith("qayta topshiring."))


if __name__ == "__main__":
    unittest.main()
