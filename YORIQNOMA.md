# Inspektor robot — foydalanuvchi yo'riqnomasi

Robot inspektor.stat.uz dagi "Biznesni ro'yxatga olish" hisobotlarini avtomatik o'qiydi,
tekshiradi, izoh yozadi va (siz tasdiqlaganingizdan keyin) qabul qiladi yoki qaytaradi.

Hamma narsa **tugmalar bilan** boshqariladi — PowerShell'da buyruq yozish shart emas.

---

## 1. Birinchi marta o'rnatish (bir marta)

1. Papkadagi **`Ornatish.bat`** faylini ikki marta bosing.
2. Oynada o'rnatish tugashini kuting (bir necha daqiqa). Oxirida "O'rnatish tugadi" chiqadi.
3. Xohlasangiz **`Yorliq-yaratish.bat`** ni bosing — ish stolida "Inspektor robot" yorlig'i paydo bo'ladi.

> O'rnatishda xatolik chiqsa, oynadagi matnni administratoringizga yuboring.

## 2. Sozlash (bir marta)

1. Papkadagi **`.env`** faylini Notepad'da oching (yo'q bo'lsa, `Ornatish.bat` uni o'zi yaratadi).
2. Faqat shu ikki qatorni o'zingiznikiga moslang:
   - `ORG_INN=...` — sizning statistika boshqarmangiz STIR raqami.
   - `SECTOR=agriculture` — siz ishlaydigan tarmoq (qishloq xo'jaligi). Boshqasi kerak bo'lsa:
     `industry` (sanoat), `construction` (qurilish), `trade` (savdo), `services` (xizmatlar),
     bo'sh qoldirsangiz — hammasi.
3. Saqlang va yoping.

## 3. Kundalik ish

**`Robot.bat`** ni (yoki ish stolidagi yorliqni) ikki marta bosing — oyna ochiladi.

### Tugmalar

| Tugma | Nima qiladi |
|---|---|
| **1. Kirish (OneID)** | Brauzer ochiladi. Siz **o'zingiz** OneID orqali login/parolingiz bilan kirasiz va tashkilotni tanlaysiz. Kirish bir marta — keyin sessiya saqlanib turadi. |
| **2. Sinov (bosilmaydi)** | Robot hisobotlarni o'qiydi va tahlil qiladi, lekin saytda **hech narsa bosmaydi**. Natijani jurnalda ko'rasiz. |
| **3. Ishga tushirish** | Robot haqiqatda ishlaydi: har bir hisobotni oladi, izoh yozadi va **sizdan so'ragach** qabul qiladi yoki qaytaradi. |
| **To'xtatish** | Joriy hisobot tugagach robot to'xtaydi. |
| **Dashboard** | Brauzerda jadval ochiladi: qaysi hisobotlar ko'rilgan, nima qaror qilingan. |

### Parol haqida — muhim

- Robot **hech qachon** login/parolingizni so'ramaydi va saqlamaydi.
- Parolni **faqat** OneID'ning o'z rasmiy sahifasiga yozasiz (ko'k "OneID" oynasi).
- Parolingizni hech kimga, jumladan bu dasturga ham bermang.

### Tasdiqlash

Robot biror hisobotni qabul yoki qaytarishdan oldin **to'xtab**, oynada so'raydi:
izohni ko'rsatadi va **"Ha, bajar"** yoki **"Yo'q, o'tkaz"** tugmalarini beradi.
Izohni o'qib, keyin tugmani bosing. Robot siz "Ha" demaguncha hech narsa bosmaydi.

## 4. Robot qanday qaror qiladi

- **Xato topilmadi** → qabul qilsa bo'ladi.
- **Xato bor** (yig'indi mos emas, majburiy maydon bo'sh, manfiy son) → izoh bilan qaytaradi.
- **Sayt ogohlantirgan** (sariq blok) → izoh bilan qaytaradi.
- **Robot ishonchsiz** (biror savolni o'qiy olmadi, hamma ko'rsatkich 0) → siz o'zingiz ko'rishingiz uchun qoldiradi, avtomatik qaror qilmaydi.

## 5. Tez-tez beriladigan savollar

**"Kirish" bosdim, lekin oyna kutib qoldi.**
OneID SMS-kod yoki captcha so'ragan bo'lishi mumkin. Brauzer oynasida uni to'ldiring.
Kirish tugagach robot o'zi davom etadi.

**Har safar kirish kerakmi?**
Yo'q. Sessiya saqlanadi. Faqat bir necha kundan keyin OneID qayta kirishni so'rasa,
yana "Kirish" tugmasini bosasiz.

**Ikki inspektor bir vaqtda ishlasa, bir hisobotni ikkalasi oladimi?**
Yo'q. Saytda hisobotni kim birinchi "olsa", o'shaniki bo'ladi. Boshqasining roboti uni o'tkazib yuboradi.

**Xatolik chiqsa nima qilaman?**
`data\robot.log` faylini va `data\screens` papkasidagi rasmni administratoringizga yuboring.

---

## Maxfiylik va xavfsizlik

- `data\` papkasi va `.env` faylini **hech kimga bermang** — ularda sizning sessiyangiz bor.
- Dasturni boshqalarga berish uchun **`Tarqatish-arxivi-yasash.ps1`** dan foydalaning:
  u maxfiy fayllarni qo'shmasdan toza arxiv yasaydi.
- Hisobotlarni avtomatik qabul/qaytarishni boshlashdan oldin **rahbariyat ruxsatini** oling.
