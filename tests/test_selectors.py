import re
import unittest

from inspektor_bot.robot import selectors as S


class SelectorTests(unittest.TestCase):
    def test_no_raw_quotes_in_patterns(self):
        # Playwright regex'ni /source/flags ko'rinishida uzatadi; ichida ' " ` bo'lsa selektor buziladi
        for name, value in vars(S).items():
            if isinstance(value, re.Pattern):
                for ch in "'\"`":
                    self.assertNotIn(ch, value.pattern, f"{name}: {value.pattern}")

    def test_apostrophe_variants(self):
        for text in ("Ko'rish", "Koʻrish", "Ko‘rish", "Ko’rish", "Ko`rish", "Korish", "KO'RISH"):
            self.assertTrue(S.VIEW_BUTTON.search(text), text)
        self.assertTrue(S.BTN_RELEASE.search("Bo'shatish"))
        self.assertTrue(S.BTN_TAKE.search(" Olish "))
        self.assertTrue(S.BTN_TAKE.search("🔗 Olish"))
        self.assertTrue(S.BTN_ACCEPT.search("✔ Qabul qilish"))
        self.assertTrue(S.BTN_REJECT.search("↺ Qaytarish"))
        self.assertFalse(S.BTN_TAKE.search("Tanlanganlarni olish"))
        self.assertFalse(S.BTN_REJECT.search("Qaytarilgan hisobotlar"))


if __name__ == "__main__":
    unittest.main()
