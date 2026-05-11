# 📚 SellerCopilot — Documentation Index

> **למאיר:** זה המדריך לכל המסמכים שנכתבו על הפרויקט. תקרא בסדר הזה.
> **תאריך:** 2026-05-11

---

## 🟢 קרא ראשון (15 דקות)

1. **[`/PROJECT.md`](../PROJECT.md)** — מי אנחנו, מה הפרויקט, החלטות קבועות
2. **[`docs/PRD_one_pager.md`](PRD_one_pager.md)** — סיכום של המוצר בעמוד אחד

---

## 🎯 לפעולה עכשיו (אחרי שתחזור מהפגישה)

3. **[`docs/validation_surveys.md`](validation_surveys.md)** — סקרים מוכנים להעתיק ולפרסם
4. **[`docs/facebook_groups_guide.md`](facebook_groups_guide.md)** — איך להיכנס לקבוצות הפייסבוק
5. **[`docs/סיכום_עבודה_עצמאית.md`](סיכום_עבודה_עצמאית.md)** — סיכום הסבב הראשון של העבודה האוטונומית

---

## 🧠 הבנה אסטרטגית עמוקה

### מחקר שוק (4 סבבים, מסודרים כרונולוגית)
6. **[`marketing/voice_of_customer.md`](../marketing/voice_of_customer.md)** — 36 ציטוטים אמיתיים ממוכרים (קיים מקודם)
7. **[`marketing/competitor_teardowns.md`](../marketing/competitor_teardowns.md)** — מחקר תחרותי קיים (קיים מקודם)
8. **[`marketing/differentiation_research_2026_05.md`](../marketing/differentiation_research_2026_05.md)** — סבב 1: אימות הבידול
9. **[`marketing/differentiation_research_2026_05_round2.md`](../marketing/differentiation_research_2026_05_round2.md)** — סבב 2: "AI שלומד" כבר תפוס
10. **[`marketing/differentiation_research_2026_05_round3.md`](../marketing/differentiation_research_2026_05_round3.md)** — סבב 3: Anthropic Managed Agents מפתרת הכל
11. **[`marketing/competitive_deep_dive_2026_05.md`](../marketing/competitive_deep_dive_2026_05.md)** — סבב 4: Astra vs AutoPilot vs SellerCopilot

---

## 🏗️ בנייה טכנית (כשמגיעים לזה)

12. **[`docs/technical_architecture_mvp.md`](technical_architecture_mvp.md)** — ארכיטקטורה מלאה + תוכנית 10 שבועות
13. **[`docs/sample_agent_code.md`](sample_agent_code.md)** — קוד דוגמה אמיתי של הסוכן
14. **[`docs/onboarding_flow_design.md`](onboarding_flow_design.md)** — איך נראה התהליך מהפעם הראשונה ועד שיחה ראשונה
15. **[`docs/landing_repositioning_draft.md`](landing_repositioning_draft.md)** — טיוטות קופי לדף נחיתה

---

## ⚖️ ציות ורגולציה

16. **[`docs/amazon_compliance_checklist.md`](amazon_compliance_checklist.md)** — צ'קליסט Amazon Agent Policy (חובה לפני השקה)

---

## 🚨 ניהול סיכונים

17. **[`docs/risk_register.md`](risk_register.md)** — 15 סיכונים מדורגים + מיטיגציה לכל אחד

---

## 🤖 הוראות לקלוד עתידי

18. **[`/CLAUDE.md`](../CLAUDE.md)** — הוראות טכניות לסשנים עתידיים של Claude Code

---

## 📊 סטטוס המסמכים לפי שלב

### ✅ הושלם (30+ עמודי תוכן)
- כל המחקר השוק (4 סבבים)
- כל הארכיטקטורה
- כל הסקרים
- כל ניהול הסיכונים
- כל הציות

### 🟡 ממתין לאימות עם לקוחות
- בנייה של MVP
- שיווק
- תמחור סופי

### ⏳ עתידי (אחרי PMF)
- הרחבה למרקטים נוספים (UK, DE, JP)
- הרחבה לסוגי קמפיינים נוספים (Sponsored Brands, Display)
- תוכנית סוכנות white-label
- API לאינטגרציה

---

## 🎬 מה עכשיו

**אם הפרויקט נכשל באימות:** יש לך ASINInsight (CSV audit) שכבר 80% בנוי. תפיוט.

**אם הפרויקט עובר אימות:** יש לך תוכנית 10 שבועות. הכל מוכן.

**אם נתקעת:** תקרא את `risk_register.md`. הסיכוי הגבוה הוא R1 (validation) או R6 (bandwidth).

---

## 📈 מטריקות הצלחה (ל-90 הימים הקרובים)

- **שבוע 1-2:** 5+ תגובות חזקות בסקרים → אימות הבידול
- **שבוע 3-12:** MVP עם 5 design partners → הוכחת קונספט
- **חודש 4-6:** 10-50 לקוחות משלמים → $1K-$5K MRR

---

## 🔗 קבצי קוד חשובים בריפו

```
server.py                  — האפליקציה הראשית (4218 שורות)
ppc_agent.py               — שלד ה-PPC agent (533 שורות, 80% מוכן)
ppc_oauth.py               — אישור OAuth (411 שורות, מוכן)
ppc_ads_client.py          — לקוח Amazon Ads API (440 שורות, מוכן)
ppc_snapshot_fetcher.py    — מושך נתונים (305 שורות, מוכן)
templates/ppc_dashboard.html — דשבורד (סטאב, צריך עבודה)
tests/test_ppc_oauth.py    — בדיקות OAuth (4 בדיקות, עוברות)
```

---

*אם משהו לא ברור, תפתח שיחה חדשה ותגיד "פרויקט סאס". Claude יקרא את PROJECT.md ויידע מה לעשות.*
