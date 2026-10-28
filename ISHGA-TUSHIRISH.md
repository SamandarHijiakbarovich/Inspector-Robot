# Ishga tushirish — qisqa qo'llanma (o'zingiz uchun)

Dastur papkasi: `C:\Users\Test1\Documents\inspektor.stat.uz tahliliy dasdur`

Ikki yo'l bor: **A)** tugmali oyna (oson), **B)** buyruqlar bilan (PowerShell).
Kundalik ish uchun **A** ni ishlating. **B** faqat sinov yoki muammoni tekshirish uchun.

---

## A) Tugmali oyna — eng oson (tavsiya etiladi)

1. Dastur papkasini oching.
2. **`Robot.bat`** faylini ikki marta bosing. Oyna ochiladi.
3. Oynada tartib bilan:
   - **1. Kirish (OneID)** — brauzer ochiladi, OneID orqali o'zingiz kirasiz, tashkilotni tanlaysiz.
   - **2. Sinov (bosilmaydi)** — robot o'qiydi va tahlil qiladi, hech narsa bosmaydi. Avval shuni sinang.
   - **3. Ishga tushirish** — robot haqiqatda ishlaydi, har bir qabul/qaytarish oldidan sizdan so'raydi.
   - **Dashboard** — natijalarni brauzerda ko'rsatadi.

PowerShell shart emas. Buyruq yozish ham shart emas.

---

## B) Buyruqlar bilan (PowerShell)

### 1-qadam: PowerShell'ni to'g'ri papkada ochish

Dastur papkasiga kiring, yuqoridagi manzil qatoriga `powershell` deb yozib Enter bosing.
Yoki istalgan PowerShell'da quyidagini bir marta yozing:

```
cd "C:\Users\Test1\Documents\inspektor.stat.uz tahliliy dasdur"
```

### 2-qadam: Buyruqlar

Hamma buyruq `python main.py` bilan boshlanadi. Aniq kerakli buyruqlar:

| Maqsad | Buyruq |
|---|---|
| Tizimga kirish (bir marta) | `python main.py login` |
| **Sinov** — faqat o'qiydi, hech narsa bosmaydi | `python main.py run` |
| Faqat **1 ta** hisobotni sinash | `python main.py run --limit 1` |
| Aniq bir korxonani tekshirish | `python main.py run --inn 305658996` |
| **Haqiqiy ish** — har amal oldidan so'raydi | `python main.py run --mode live` |
| Bitta hisobotni haqiqiy qaytarish/qabul | `python main.py run --mode live --limit 1` |
| Dashboard (brauzerda jadval) | `python main.py dashboard` |
| Tugmali oynani ochish | `python main.py gui` |

> Eslatma: `python main.py ...` yozsangiz, dastur avtomatik `.venv` ichidagi to'g'ri Python'ga
> o'tadi. Qo'shimcha hech narsa yozish shart emas.

### 3-qadam: Robot so'raganda

`--mode live` da robot har bir qabul yoki qaytarish oldidan to'xtab so'raydi:

```
>>> Hisobot QAYTARILSINMI? [ha / yo'q / q = to'xtatish]:
```

- `ha` + Enter — robot tugmani bosadi.
- `yo'q` + Enter — bo'shatib o'tkazadi.
- `q` + Enter — bo'shatib to'xtaydi.

Robotni to'xtatish: PowerShell oynasida **Ctrl + C**.

---

## Kundalik oddiy tartib (eng ko'p ishlatadigan)

1. `Robot.bat` ni oching.
2. **Kirish** → OneID orqali kiring (sessiya saqlangan bo'lsa, bu qadam o'tkaziladi).
3. **Sinov** → robotning qarorlarini ko'ring.
4. Ishonch hosil bo'lsa → **Ishga tushirish** → har biri uchun "Ha / Yo'q".

---

## Muammo bo'lsa

- Xato chiqsa: `data\robot.log` faylini ochib, oxirgi qatorlarni o'qing.
- Robot biron tugmani topmasa: `data\screens` papkasida rasm va HTML saqlanadi.
- Qaytadan o'rnatish kerak bo'lsa: `Ornatish.bat` ni bosing.

## Hech qachon

- `.env` va `data\` ni boshqalarga bermang (ichida sizning sessiyangiz bor).
- Parolni faqat OneID'ning o'z sahifasiga yozing, dasturga emas.
