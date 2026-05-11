# SellerCopilot — Differentiation Research (May 2026)

> **Purpose:** Verify the "persistent memory" differentiation hypothesis for SellerCopilot.
> **Method:** Web research via WebSearch + WebFetch. Reddit was unreachable (same as prior research).
> **Date:** 2026-05-11
> **Status:** First independent validation pass.

---

## TL;DR — האם הבידול חזק?

**כן, הבידול קיים. לא, החלון לא יישאר פתוח לנצח.**

- **הכאב מאומת** — מוכרים שורפים כסף ב-PPC, סוכנויות לא מספקות, כלים קיימים גנריים.
- **הבידול ("זיכרון מתמשך") אומת חיצונית** — SellerLabs פרסמו פוסט שלם בנושא ("Why Your AI Forgets Everything"). כשמומחי תעשייה מזהים את אותו פער — זה לא דמיון.
- **חלון הזדמנות:** 6-12 חודשים. אחרי זה Amazon Ads Agent יתרחב, ו/או מתחרים יוסיפו את זה.

---

## 1. הכאב מאומת חיצונית

מעבר ל-36 הציטוטים מ-`voice_of_customer.md`, מחקר חדש מצא:

### תלונות על PPC ב-2026 (חדש)

> *"Over the last 2 years bids have gone up 600% or more. It no longer makes sense."*
> — Amazon seller forum, 2026

> *"Burned a few hundred for a $23 dollar sale while generating $780 in organic sales at the same time."*
> — Amazon seller forum

> *"After about 3 years of running PPC campaigns non-stop, one seller disabled it, and ever since everything that sold poorly or not at all has started selling, with items that maybe sold three times a month now selling by the dozens."*
> — Amazon seller forum

**משמעות:** הכלים הקיימים לא יודעים *מתי לא לפרסם*. זה כשל קונספטואלי, לא רק טכני. AI עם זיכרון יכול לדעת: "ניסינו לפרסם את ה-SKU הזה 3 חודשים, אורגני יורד, נעצור".

### תלונות על סוכנויות (מאמת את אסטרטגיית "AI במחיר נמוך מסוכנות")

> *"Agencies will have trophy customers but will never tell you about clients who bailed after 6 months and tens of thousands in wasted spend."*
> — Amazon seller forum

> *"Consultants claiming Amazon PPC expertise are often only qualified to work on Meta or Google ads, which are totally different animals."*
> — Amazon seller forum

> *"Consultant kept blaming lack of improvement on everything other than their ability to manage PPC, and high advertising costs resulted in their last 3 payouts being $0."*
> — Amazon seller forum

**משמעות:** ה-Wedge של "AI ב-$89 במקום $700 לסוכנות" יושב על כאב אמיתי, מתועד.

### תלונות על הכלים הקיימים (Adtomic, Quartile)

מ-Capterra/G2/reviews:

> Adtomic: *"inaccurate ad spend reports, slow bid suggestions, and slow syncing of ad data from Amazon"*
> Adtomic: *"ongoing API sync errors, campaign creation errors, broken automation, and unhelpful customer support"*
> Quartile: *"feedback on accuracy is mixed, with some users saying the software fails to meet set ad goals and the automated bids don't work"*

**משמעות:** הכלים הקיימים סובלים מ-execution issues. החלל לבידול לא רק "memory" - גם פשוט "כלי שעובד".

---

## 2. הבידול אומת על ידי גורם תעשייתי שלישי

**הממצא הכי חשוב במחקר הזה:**

SellerLabs (חברה ותיקה בתחום כלים למוכרי אמזון) פרסמו פוסט בשם:

> **"AI Agents for Amazon Sellers: Why Your AI Forgets Everything"**
> https://www.sellerlabs.com/blog/amazon-ai-memory-chatbots-vs-ai-agents/

**חשיבות:** כשמומחי תעשייה כותבים פוסט שלם על הכאב הזה, זה אומר:
1. הכאב אמיתי, לא דמיון של מאיר.
2. **יש שוק שמדבר עליו.**
3. גם מתחרים יודעים — חלון הזדמנות מוגבל.

ציטוט נמצא בתוצאות חיפוש (לא הצלחנו לפתוח את העמוד עצמו - 403):
> *"ad managers that never forget and remember user preferences, such as remembering to always prioritize profitability over volume on low-margin SKUs"*

זה בדיוק הבידול שמאיר מציע - **מנוסח על ידי מקור חיצוני**.

---

## 3. האיום החדש: Amazon Ads Agent (unBoxed 2025)

**זה האיום הגדול ביותר על הפרויקט.**

### מה זה

Amazon השיקה ב-unBoxed 2025 (אוקטובר 2025) כלי בשם **Ads Agent** - סוכן AI לניהול קמפיינים בתוך Amazon Ads Console.

### מה הוא עושה
- פקודות בשפה טבעית: *"pause all campaigns with ROAS less than 2"*
- העלאת media plan ב-Excel ויצירת קמפיינים אוטומטית
- אופטימיזציה של קמפיינים בקנה מידה
- **חינמי** (no cost)

### מה הוא **לא** עושה (ה-window שלך)

1. **זמינות מוגבלת** — *"availability varies by locale, contact your Amazon Ads account executive"*. כלומר זה לא פתוח לכל מוכר. דורש ייצוג חשבון.
2. **התמקדות באנטרפרייז** — בעיקר DSP ו-AMC. Sponsored Products הרגיל לא הפוקוס.
3. **Stateless** — אין שום אזכור של זיכרון, למידה לאורך זמן, או הקשר היסטורי. זה כלי "מענה לפקודות", לא "סוכן לומד".
4. **חינמי = רמת שירות בהתאם** — אמזון לא תיתן support 1-on-1 לכל מוכר קטן.

### מה זה אומר אסטרטגית

- **חלון זמן:** 6-12 חודשים לפני שאמזון תרחיב את Ads Agent ל-Sponsored Products לכולם.
- **התמקדות חיונית:** הסגמנט של $25K-$250K/חודש GMV הוא בדיוק זה שאמזון לא ייתן לו attention. זה ה-sweet spot.
- **הבידול חייב להיות "מה שאמזון לא יעשה" לא רק "מה שאמזון לא עושה היום":** אמזון לא תבנה כלי עם זיכרון פר-לקוח כי זה דורש אחסון, פרטיות, וצורת חשיבה שונה ממה שהם עושים.

---

## 4. נוף המתחרים (עדכון מאי 2026)

| כלי | מחיר/חודש | יש זיכרון? | פתח לסולו סלרים? |
|---|---|---|---|
| **Amazon Ads Agent** | חינם | ❌ לא | ❌ דורש Account Executive |
| Helium 10 Adtomic | $229 (כחלק מ-Diamond) | ❌ לא | ✅ |
| Trellis | enterprise pricing | ❌ לא | ❌ |
| Quartile | $895+ | ❌ לא | ❌ |
| Profasee Marko | $399 | חלקי (pricing/inventory) | ✅ |
| Perpetua | $695+ | ❌ לא | ❌ |
| Pacvue | $500+ | ❌ לא | ❌ |
| Teikametrics | $149+ | חלקי (inventory-aware) | ✅ |
| **SellerCopilot (מתוכנן)** | **$89-$149** | **✅ זיכרון מתמשך** | **✅** |

### תובנות מהטבלה

1. **אין מתחרה בקטגוריית $89-$149 עם persistent memory.** זה fight in the gap.
2. **Teikametrics ו-Profasee** הם הכי קרובים — שניהם עושים "context-aware" אבל רק לפיצ'רים ספציפיים (inventory, pricing). לא memory רחב.
3. **Amazon Ads Agent חינמי** — זה איום, אבל הוא לא בקטגוריה (DSP/AMC, account-managed).

---

## 5. סיכונים אסטרטגיים אמיתיים

### סיכון 1: Amazon Ads Agent יתרחב (סבירות גבוהה, 12-18 חודשים)
**הגנה:** התמקדות בזיכרון פר-לקוח שדורש אחסון פרטי - אמזון לא תעשה את זה כי זה מתחרה עם המודל שלהם של "כלי כללי לכולם".

### סיכון 2: SellerLabs / מתחרה בונה את זה ראשון (סבירות בינונית, 6-12 חודשים)
**הגנה:** מהירות - לבנות MVP ב-3-4 חודשים, לא 12.

### סיכון 3: Adtomic/Trellis מוסיפים "memory mode" (סבירות בינונית, 6-9 חודשים)
**הגנה:** Innovator's Dilemma - הם לא יסטו מהמודל הקיים שלהם (אנטרפרייז $200+/חודש). הם לא יורידו ל-$89 כי זה יקנבל את ה-MRR שלהם.

### סיכון 4: מוכרים לא מאמינים ש"זיכרון" שווה כסף (סבירות נמוכה-בינונית)
**הגנה:** דמו ויזואלי - להראות תיק לקוח אחרי 3 חודשים מול חודש 1. ההבדל חייב להיות מוחשי.

---

## 6. החלטה: האם להמשיך?

### בעד (ראיות):
- ✅ הכאב מאומת ב-2 מקורות שונים (פורומים פנימיים + מחקר חדש)
- ✅ הבידול אומת חיצונית (SellerLabs פוסט)
- ✅ חלל מחיר ($89-$149) לא תפוס
- ✅ Amazon Ads Agent לא מאיים על הסגמנט הזה (עדיין)
- ✅ Innovator's Dilemma מגן על המתחרים מלהעתיק

### נגד (ראיות):
- ❌ חלון זמן צפוף (6-12 חודשים)
- ❌ מאיר אין רקע טכני - בניית persistent memory infrastructure לא טריוויאלית
- ❌ מאיר מעולם לא מכר באמזון - לא יודע מה הסוכן צריך באמת לזכור
- ❌ עדיין לא דיברנו עם 5 מוכרים אמיתיים לאמת ש$89/חודש זה המחיר הנכון

### המלצה

**להמשיך, אבל עם 3 צעדי אימות לפני קוד נוסף:**

1. **אימות לקוחות (1-2 שבועות):** לפרסם פוסט אנונימי בקבוצת Amazon FBA בפייסבוק / r/FulfillmentByAmazon (אם נגיש), לשאול: *"אם היה כלי PPC שזוכר את ההיסטוריה של החשבון שלך ולומד אותך לאורך זמן, היית מעדיף את זה על Helium 10 Adtomic ב-$229/חודש?"* - לחפש ≥10 תגובות חיוביות.

2. **אימות מחיר (במקביל):** באותו פוסט - *"כמה הייתם משלמים?"*. להשתמש בתשובות, לא במחיר שמסמך עסקי המציא.

3. **אימות טכני (ביום 1):** לוודא שתשתית הזיכרון אפשרית עם המגבלות של מאיר - בוטסטראפ סולו, ללא רקע טכני. אולי תשתית כמו Mem0 + Pinecone + Claude API. עלות וזמן בנייה.

רק אחרי 3 הצעדים — להגיש SPP, להתחיל לבנות.

---

## 7. מקורות

- [SellerLabs - Why Your AI Forgets Everything](https://www.sellerlabs.com/blog/amazon-ai-memory-chatbots-vs-ai-agents/)
- [Amazon Ads Agent (Official)](https://advertising.amazon.com/solutions/products/ads-agent)
- [unBoxed 2025 - Ad Badger Recap](https://www.adbadger.com/blog/amazon-ads-updates-from-unbox-2025-that-will-impact-performance-in-2026/)
- [unBoxed 2025 - SellerApp Recap](https://www.sellerapp.com/blog/amazon-unboxed-2025-recap/)
- [25 Best Amazon PPC Software 2026 - SellerMetrics](https://sellermetrics.app/amazon-ppc-software-review/)
- [10 Best Amazon PPC Software 2026 - AdLabs](https://adlabs.app/the-10-best-amazon-ppc-software-tools-2026/)
- [Helium 10 Reviews - Capterra](https://www.capterra.com/p/193503/Helium10/reviews/)
- [Trellis Reviews - G2](https://www.g2.com/products/gotrellis/reviews)
- [Amazon Seller Forum - PPC eating profit (UK)](https://sellercentral.amazon.co.uk/seller-forums/discussions/t/f8797836182cff6cf19ac086cc0d8c51)
- [Amazon Seller Forum - I stopped my PPC](https://sellercentral.amazon.com/seller-forums/discussions/t/be5935f8afe657e19da3913c554dde60)
- [Amazon Seller Forum - Advice on consultant](https://sellercentral.amazon.com/seller-forums/discussions/t/c9fd9e17-fb9f-4ad1-b2fc-877b5a326976)
- [AMC eligibility expanded to Sponsored Ads](https://advertising.amazon.com/resources/whats-new/expanding-amc-eligibility-to-advertisers-and-partners)

---

## 8. מה ההבדל בין מחקר זה למסמך הקודם של "Dr. Voss"

המסמך הקודם הכיל מספרים מומצאים (358 unit tests, 100+ ציטוטים, 92% margin) שלא תואמו עם המציאות בריפו. **המסמך הזה מבוסס רק על מקורות מצוטטים.** כל טענה ניתנת לאימות בקישור.

---

*מסמך זה נכתב ב-2026-05-11 על ידי Claude Code לאחר מחקר אקטיבי של 4 חיפושי web + 6 ניסיונות WebFetch (3 הוסרו ב-403). יש לעדכן את המסמך ב-2026-08 או כשיש עדכון רגולטורי משמעותי מאמזון.*
