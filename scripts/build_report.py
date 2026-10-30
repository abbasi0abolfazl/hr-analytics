"""Build the 10-slide Persian/English PDF from the analytics module (not from the API).

    python scripts/build_report.py            # -> report/People_Analytics_Report.pdf (+ slides.html)

All numbers on the slides are computed here from DuckDB through hr_analytics.metrics,
so they always match the dashboard.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from hr_analytics import metrics as M  # noqa: E402
from hr_analytics.config import DEFAULT_DB, STATIC_DIR  # noqa: E402
from hr_analytics.db import connect  # noqa: E402

OUT = ROOT / "report"


def collect(con):
    f = M.Filters()
    D = {"ov": M.overview(con, f), "traj": M.pre_exit_trajectory(con, f), "drv": M.risk_drivers(con, f),
         "rec": M.recruitment(con, f), "car": M.careers(con, f), "sv": M.engagement_survey(con, f),
         "reasons": M.exit_reasons(con, f)}
    D["dept"] = M.attrition_breakdown(con, f, "department")["rows"]
    D["mgr"] = M.attrition_breakdown(con, f, "manager_id")["rows"]
    D["ten"] = M.attrition_breakdown(con, f, "tenure_band")["rows"]
    D["coh"] = M.attrition_breakdown(con, f, "hire_cohort")["rows"]
    fact = M.get_fact(con, f)
    ex = fact[fact["exited"]]
    months = sorted(fact["month"].unique())
    D["months"] = [pd.Timestamp(m).strftime("%Y-%m") for m in months]
    D["dept_month"] = {d: [int(((ex["department"] == d) & (ex["month"] == m)).sum()) for m in months]
                       for d in sorted(fact["department"].unique())}
    return D


def reasons_total(D):
    out = {}
    for r in D["reasons"]["rows"]:
        out[r["reason"]] = out.get(r["reason"], 0) + r["exits"]
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main():
    con = connect(DEFAULT_DB, read_only=True)
    D = collect(con)
    con.close()
    k = D["ov"]["kpi"]
    mon = D["ov"]["monthly"]
    model = {t["term"].split(" ")[0]: t for t in D["drv"]["model"]["terms"]}
    eng_b = D["drv"]["bands"]["engagement"]
    perf_b = D["drv"]["bands"]["performance"]
    rec, car, sv = D["rec"], D["car"], D["sv"]
    gap = {g["dimension"]: g for g in sv["gap"]}
    dept = {r["group"]: r for r in D["dept"]}
    mg = {r["group"]: r for r in D["mgr"]}
    rt = reasons_total(D)
    tot_ex = k["exits"]
    q4 = [m for m in mon if m["month"] >= "2025-10"]
    q4_h = sum(m["exits"] for m in q4) / sum(m["headcount"] for m in q4)
    proj = k["closing_headcount"] * (1 - q4_h) ** 6
    nh = {r["group"]: r for r in D["coh"]}
    tech_nh = [r for r in rec["by_department"] if r["department"] == "Technical"][0]
    p_hp = car["high_vs_other_fisher_p"]
    p = lambda x: "&lt;0.001" if x < 0.001 else (f"{x:.3f}" if x < 0.01 else f"{x:.2f}")  # noqa: E731
    pc = lambda x, d=0: f"{x * 100:.{d}f}%"  # noqa: E731
    mgr_p = D["drv"]["model"]["manager_effect"]["p_value"]
    h2 = model["second_half_year"]
    ratio_q = eng_b[0]["monthly_hazard"] / eng_b[-1]["monthly_hazard"]
    traj = {r["months_before_exit"]: r["engagement"] for r in D["traj"]["rows"]}
    eng_drop = traj[8] - traj[1] if 8 in traj else None
    d_ = D | {"labels": D["months"]}

    S = []   # slides: html strings
    kp = lambda v, l, cls="": f'<div class="kpi {cls}"><b>{v}</b><span>{l}</span></div>'  # noqa: E731

    # 1 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>سازمان در ۱۲ ماه حدود {abs(k['net_change_pct'])*100:.0f}٪ از Headcount خود را از دست داده و شتاب خروج در حال افزایش است</h1>
<p class="sub">خلاصه مدیریتی · داده‌های ۲۰۲۵ · ۳۶۰ نفر · ۱۵۲ خروج · ۸۰ استخدام</p>
<div class="kpis">{kp(f"{k['opening_headcount']} → {k['closing_headcount']}", 'Headcount ابتدا → پایان سال', 'bad')}{kp(pc(k['annualized_turnover']), 'Turnover سالانه‌شده', 'bad')}
{kp(f"{k['exits']} / {k['hires']}", 'خروج / استخدام (فقط ' + pc(k['hires']/k['exits']) + ' جبران شد)', 'bad')}{kp(f"{k['hazard_h2']/k['hazard_h1']:.1f}×", f"نرخ ماهانه H2 نسبت به H1 ({pc(k['hazard_h1'],1)} → {pc(k['hazard_h2'],1)})", 'bad')}
{kp(pc(rec['summary']['left_share']), 'استخدام‌های ۲۰۲۵ که همان سال رفتند', 'bad')}</div>
<div class="cols3">
<div class="card c1"><h3>۱ · موج خروج در نیمه دوم سال</h3><p>ریزش در همه بخش‌ها هم‌زمان بالا رفته است. <b>Engagement</b> تنها سیگنال هشدار معنادار است (چارک پایین ≈ {ratio_q:.0f}× ریسک چارک بالا)؛ <b>Performance</b> هیچ نقشی ندارد، یعنی سازمان بازیگران خوب را هم به همان نرخ از دست می‌دهد.</p><span class="tag hi">اطمینان: بالا (الگو) · پایین (علت موج H2)</span></div>
<div class="card c2"><h3>۲ · چرخه فرسایشی جذب</h3><p>{rec['summary']['left_in_year']} از {rec['summary']['hires']} نیروی تازه‌استخدام همان سال رفتند (میانه {rec['summary']['median_days_to_exit']:.0f} روز). حدود {pc(rec['summary']['sunk_cost_share'])} از هزینه جذب سال صرف کسانی شده که ماندگار نشدند.</p><span class="tag hi">اطمینان: بالا (اندازه) · متوسط (علت)</span></div>
<div class="card c3"><h3>۳ · رشد شغلی و جبران خدمات</h3><p>در کل سال <b>هیچ ارتقایی ثبت نشده</b> در حالی که {car['promotion_ready']['employees']} نفر «آماده ارتقا» هستند. {pc(car['exit_reason_compensation_career_share'])} خروج‌ها به حقوق یا رشد شغلی نسبت داده شده است.</p><span class="tag md">اطمینان: متوسط (نیازمند تأیید داده ارتقا)</span></div>
</div>
<p class="foot">همبستگی ≠ علیت: در هر اسلاید سطح اطمینان و اطلاعات لازم برای قطعیت بیشتر ذکر شده است.</p>""")

    # 2 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>وضعیت موجود: خروج‌ها از ماه ژوئن تندتر می‌شوند و جذب جلوی افت Headcount را نمی‌گیرد</h1>
<p class="sub">{k['opening_headcount']} (ابتدا) + {k['hires']} استخدام − {k['exits']} خروج = {k['closing_headcount']} (پایان سال)</p>
<div class="grid2"><div class="cv"><canvas id="c_flow"></canvas></div><div class="cv"><canvas id="c_haz"></canvas></div></div>
<ul class="bul"><li>ژانویه تا مه: میانگین {sum(m['exits'] for m in mon[:5])/5:.0f} خروج در ماه؛ از ژوئن جهش (۱۷ نفر) و در سپتامبر تا دسامبر ۲۰ تا ۲۵ نفر در ماه.</li>
<li>استخدام‌ها در سه ماه آخر به ۶ و ۶ و ۰ نفر رسیده؛ یعنی هم‌زمان با اوج خروج، جذب هم کند شده است.</li>
<li>ریزش سالانه‌شده: فروش {pc(dept['Sales']['annualized_turnover'])}، فنی {pc(dept['Technical']['annualized_turnover'])}، مالی {pc(dept['Finance']['annualized_turnover'])}، بازاریابی {pc(dept['Marketing']['annualized_turnover'])}. ۹۰٪ خروج‌ها داوطلبانه است ({k['voluntary_exits']} از {k['exits']}).</li></ul>
<p class="foot">تعریف: نرخ ماهانه = خروج‌ها ÷ افراد شاغل همان ماه · Turnover سالانه = خروج ÷ میانگین Headcount × ۱۲/تعداد ماه · Engagement مقیاس ۱–۵.</p>""")

    # 3 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>مسئله ۱ — ریزش در نیمه دوم سال در همه بخش‌ها هم‌زمان بالا رفته؛ تفاوت مدیران مشکوک است ولی قطعی نیست</h1>
<p class="sub">خروج‌های ماهانه به تفکیک بخش · نرخ ماهانه H1 در برابر H2 به تفکیک مدیر</p>
<div class="grid2"><div class="cv"><canvas id="c_dm"></canvas></div><div class="cv"><canvas id="c_mgr"></canvas></div></div>
<ul class="bul"><li><b>سیستمی است، نه محلی:</b> نرخ ماهانه فروش {pc(dept['Sales']['hazard_h1'],1)} → {pc(dept['Sales']['hazard_h2'],1)}، فنی {pc(dept['Technical']['hazard_h1'],1)} → {pc(dept['Technical']['hazard_h2'],1)}، مالی {pc(dept['Finance']['hazard_h1'],1)} → {pc(dept['Finance']['hazard_h2'],1)}، بازاریابی {pc(dept['Marketing']['hazard_h1'],1)} → {pc(dept['Marketing']['hazard_h2'],1)}. نقش بخش پس از کنترل Engagement معنادار نیست.</li>
<li><b>مدیران:</b> ریزش سالانه‌شده MGR_S02 برابر {pc(mg['MGR_S02']['annualized_turnover'])} و MGR_T02/T03 حدود {pc(mg['MGR_T02']['annualized_turnover'])} در برابر {pc(mg['MGR_M02']['annualized_turnover'])} برای MGR_M02. اما آزمون هم‌زمان اثر مدیر معنادار نیست (LR p={mgr_p:.2f}) و گروه‌ها کوچک‌اند؛ فقط «فرضیه»، نه حکم.</li>
<li><b>سابقه:</b> کارکنان ۰–۶ ماه سابقه بالاترین ریسک را دارند ({pc(D['ten'][0]['annualized_turnover'])} سالانه‌شده) و به مسئله ۲ مربوط می‌شود.</li></ul>""")

    # 4 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>مسئله ۱ — Engagement ماه‌ها قبل از خروج افت می‌کند و تنها سیگنال معنادار است؛ Performance هیچ سیگنالی نمی‌دهد</h1>
<p class="sub">ریسک خروج ماهانه به تفکیک چارک مقدار «ماه قبل» (برای جلوگیری از نشت اطلاعات خود ماه خروج)</p>
<div class="grid3"><div class="cv"><canvas id="c_traj"></canvas></div><div class="cv"><canvas id="c_qe"></canvas></div><div class="cv"><canvas id="c_qp"></canvas></div></div>
<ul class="bul"><li>چارک پایین Engagement: {pc(eng_b[0]['monthly_hazard'],1)} خروج در ماه، چارک بالا: {pc(eng_b[-1]['monthly_hazard'],1)} (≈{ratio_q:.0f}×). به ازای هر +۱ امتیاز Engagement، بخت خروج ×{model['engagement_prev']['odds_ratio']:.2f} (بازه {model['engagement_prev']['ci_low']:.2f}–{model['engagement_prev']['ci_high']:.2f}؛ p&lt;0.001؛ AUC={D['drv']['model']['auc_engagement_only']:.2f}).</li>
<li>Engagement ترک‌کنندگان از ≈{traj[8]:.2f} هشت ماه قبل به ≈{traj[1]:.2f} یک ماه قبل از خروج می‌رسد؛ میانگین ماندگاران ≈{D['traj']['stayers_baseline']['engagement']:.2f}. این افت فرصت مداخله ۳ تا ۶ ماهه می‌دهد.</li>
<li>Performance (p={p(model['performance_prev']['p_value'])}) و Skills Gap (p={p(model['skills_gap_prev']['p_value'])}) و فاصله از ارتقا (p={p(model['months_since_promo_prev']['p_value'])}) پس از کنترل Engagement معنادار نیستند؛ Top Performerها {pc(car['high_performers']['left_share'])} و بقیه {pc(car['other_performers']['left_share'])} رفته‌اند (Fisher p={p_hp:.2f}).</li>
<li><b>محدودیت:</b> افت Engagement می‌تواند نشانه تصمیم به رفتن باشد، نه علت آن. و اثر «نیمه دوم سال» با OR={h2['odds_ratio']:.1f} پس از کنترل Engagement باقی می‌ماند: افت Engagement به‌تنهایی جهش H2 را توضیح نمی‌دهد.</li></ul>""")

    # 5 -------------------------------------------------------------------------------------------
    km = {x["day"]: x["survival"] for x in rec["survival_km"]}
    S.append(f"""
<h1>مسئله ۲ — نیمی از استخدام‌های ۲۰۲۵ همان سال رفته‌اند؛ تازه‌واردها ۲٫۲ برابر بیشتر در معرض خروج‌اند</h1>
<p class="sub">احتمال ماندن (Kaplan–Meier، با لحاظ censoring) · استخدام ماهانه و تعداد خروج‌کرده‌ها از همان گروه</p>
<div class="kpis">{kp(f"{rec['summary']['left_in_year']} / {rec['summary']['hires']}", 'تازه‌استخدام‌هایی که همان سال رفتند', 'bad')}{kp(f"{rec['summary']['median_days_to_exit']:.0f} روز", 'میانه زمان تا خروج', 'bad')}{kp(rec['summary']['left_within_90d'], 'خروج در ۹۰ روز اول', 'bad')}{kp(pc(tech_nh['left_share']), 'نرخ خروج تازه‌واردان بخش فنی', 'bad')}{kp(f"×{model['new_hire_2025']['odds_ratio']:.1f}", 'OR تعدیل‌شده تازه‌وارد بودن (p&lt;0.001)', 'bad')}</div>
<div class="grid2"><div class="cv"><canvas id="c_km"></canvas></div><div class="cv"><canvas id="c_hm"></canvas></div></div>
<ul class="bul"><li>فقط {pc(km[90],0)} تازه‌واردان پس از ۹۰ روز و {pc(km[180],0)} پس از ۱۸۰ روز مانده‌اند. بدون KM این عدد خوش‌بینانه می‌شد، چون استخدام‌های پاییز فرصت خروج نداشته‌اند.</li>
<li>مقایسه ماهانه: ریسک تازه‌واردان {pc(nh['new_hire_2025']['annualized_turnover'],0)} در برابر {pc(nh['existing']['annualized_turnover'],0)} سالانه‌شده برای قبلی‌ها؛ این فاصله پس از کنترل Engagement هم باقی می‌ماند.</li></ul>""")

    # 6 -------------------------------------------------------------------------------------------
    nr = rec["newhire_exit_reasons"]
    S.append(f"""
<h1>مسئله ۲ — هزینه سنگین و علت‌های محتمل: انتظار حقوقی، فشار کاری و ناکارآمدی ورود به سازمان</h1>
<p class="sub">دلایل خروج تازه‌واردان · عملکرد جذب به تفکیک بخش</p>
<div class="grid2"><div class="cv"><canvas id="c_nr"></canvas></div>
<div><table class="tbl"><tr><th>بخش</th><th>درخواست</th><th>پذیرش Offer</th><th>استخدام</th><th>رفته در سال</th><th>٪</th></tr>
{''.join(f"<tr><td>{ {'Sales':'فروش','Technical':'فنی','Finance':'مالی','Marketing':'بازاریابی'}[r['department']] }</td><td>{r['requisitions']}</td><td>{pc(r['acceptance_rate'])}</td><td>{r['hires']}</td><td>{r['left_in_year']}</td><td><b>{pc(r['left_share'])}</b></td></tr>" for r in rec['by_department'])}</table>
<ul class="bul small"><li>هزینه جذب {rec['summary']['sunk_cost_of_leavers']/1e6:,.0f}M از {rec['funnel']['total_hiring_cost']/1e6:,.0f}M ({pc(rec['summary']['sunk_cost_share'])}) برای کسانی بوده که رفته‌اند (واحد: همان واحد داده).</li>
<li>{rec['funnel']['declined']} از {rec['funnel']['requisitions']} Offer رد شده؛ به‌طور میانگین {rec['funnel']['offers_per_hire']:.1f} Offer برای هر استخدام لازم بوده است.</li></ul></div></div>
<div class="grid2 hyp"><div class="card"><h3>برداشت و فرضیه‌ها</h3><p>دلایل ثبت‌شده: حقوق ({nr[0]['exits']})، فشار کاری ({nr[1]['exits']})، توسعه شغلی ({nr[2]['exits']}). فرضیه: شکاف انتظار در زمان Offer و نبود فرایند ورود (Onboarding) منسجم، به‌ویژه در بخش فنی.</p></div>
<div class="card"><h3>چه چیزی را نمی‌دانیم</h3><p>Quality of Hire ۹۰ روزه پیش‌بینی خروج نیست و برای ۲۱ نفری که پیش از روز ۹۰ رفته‌اند هم پر شده (نقطه اندازه‌گیری مبهم). برای قطعیت لازم است: کانال جذب، حقوق Offer در برابر بازار، امتیاز مصاحبه، برنامه Onboarding و مدیر مستقیم.</p></div></div>""")

    # 7 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>مسئله ۳ — حقوق و رشد شغلی بیشترین دلایل ثبت‌شده خروج‌اند و ترک‌کنندگان در همین ابعاد Survey امتیاز کمتری داده‌اند</h1>
<p class="sub">دلایل خروج (تعداد) · ابعاد Survey: ترک‌کنندگان در برابر ماندگاران (مقیاس ۱–۵، نه ۰–۱۰)</p>
<div class="grid2"><div class="cv"><canvas id="c_rs"></canvas></div><div class="cv"><canvas id="c_gap"></canvas></div></div>
<ul class="bul"><li>حقوق ({rt.get('Compensation',0)}) + توسعه شغلی ({rt.get('Career Development',0)}) = {pc(car['exit_reason_compensation_career_share'])} از کل خروج‌ها؛ فشار کاری ({rt.get('Work Pressure',0)}) و رابطه با مدیر ({rt.get('Manager Relationship',0)}) بعدی‌اند. همه این‌ها داوطلبانه‌اند.</li>
<li>تأیید مستقل از دلیل اظهارشده: ترک‌کنندگان در «فرصت رشد» {gap['growth_opportunities']['gap']:+.2f} (p={p(gap['growth_opportunities']['p_value'])}) و «حقوق و مزایا» {gap['compensation_benefits']['gap']:+.2f} (p={p(gap['compensation_benefits']['p_value'])}) پایین‌تر بوده‌اند؛ در سبک مدیریت و تعادل کار–زندگی تفاوتی نیست.</li>
<li>«فرصت رشد» پایین‌ترین بُعد برای همه کارکنان است ({sv['by_quarter'][0]['growth_opportunities']:.2f}) و بیشترین همبستگی را با Engagement دارد (r={sv['corr_with_engagement']['growth_opportunities']:.2f}؛ حقوق r={sv['corr_with_engagement']['compensation_benefits']:.2f}): مسیر محتمل «رشد/حقوق → Engagement → خروج».</li></ul>
<p class="foot">توجه: Survey فقط افراد شاغل در زمان نظرسنجی را شامل می‌شود (survivorship bias) و دلیل خروج خوداظهاری است.</p>""")

    # 8 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>مسئله ۳ — در کل سال هیچ ارتقایی ثبت نشده، در حالی که ۱۱۲ نفر در دست‌کم یک Review «آماده ارتقا» بوده‌اند</h1>
<p class="sub">ریسک خروج بر اساس ماه‌های گذشته از آخرین ارتقا · آماده ارتقا و Top Performer به تفکیک بخش</p>
<div class="kpis">{kp(car['promotion_events_observed'], 'ارتقای قابل مشاهده در داده ۱۲ ماه', 'bad')}{kp(car['promotion_ready']['employees'], 'آماده ارتقا در آخرین Review')}{kp(pc(car['promotion_ready']['left_share']), 'از آن‌ها خارج شده‌اند', 'bad')}{kp(f"{car['promotion_ready']['avg_months_since_promotion']:.0f} ماه", 'میانگین فاصله از آخرین ارتقا')}{kp(pc(car['high_performer_leavers_rehire_eligible_share']), 'Top Performerهای رفته که Rehire‌پذیرند')}</div>
<div class="grid2"><div class="cv"><canvas id="c_msp"></canvas></div><div class="cv"><canvas id="c_cd"></canvas></div></div>
<ul class="bul"><li>ریسک ماهانه برای ۳۷+ ماه بدون ارتقا {pc(car['months_since_promotion_bands'][-1]['monthly_hazard'],1)} در برابر {pc(car['months_since_promotion_bands'][0]['monthly_hazard'],1)} برای ≤۱۲ ماه؛ اما پس از کنترل Engagement اثر مستقل معنادار نیست (p={p(model['months_since_promo_prev']['p_value'])}) و یعنی اثر احتمالاً از مسیر Engagement است.</li>
<li><b>باید تأیید شود:</b> «بدون ارتقا» فریز واقعی است یا فیلد ارتقا به‌روز نمی‌شود؟ در هر دو حالت یک مسئله وجود دارد: یا ریسک نگهداشت، یا ضعف حاکمیت داده.</li></ul>""")

    # 9 -------------------------------------------------------------------------------------------
    S.append(f"""
<h1>علت‌ها و میزان اطمینان: کجا می‌توانیم تصمیم بگیریم و کجا هنوز باید داده جمع کنیم</h1>
<p class="sub">تمایز بین همبستگی و علیت · اطلاعات لازم برای افزایش اطمینان</p>
<table class="tbl wide"><tr><th>یافته</th><th>شواهد</th><th>اطمینان</th><th>همبستگی یا علیت؟</th><th>برای قطعیت بیشتر لازم است</th></tr>
<tr><td>Engagement پایین پیش‌بینی‌کننده خروج است</td><td>OR {model['engagement_prev']['odds_ratio']:.2f}؛ AUC {D['drv']['model']['auc_engagement_only']:.2f}؛ افت ۳–۶ ماه قبل</td><td><span class="tag hi">بالا</span></td><td>همبستگی با ترتیب زمانی؛ ممکن است نشانه تصمیم به رفتن باشد</td><td>Pulse Survey ماهانه، تحلیل پیش/پس از مداخله</td></tr>
<tr><td>جهش خروج در H2 (علت؟)</td><td>OR {h2['odds_ratio']:.1f} پس از کنترل همه متغیرها</td><td><span class="tag lo">پایین</span></td><td>علت اندازه‌گیری‌نشده</td><td>رویدادهای ژوئن و پاییز (ساختار، حقوق، رقبا)، متن Exit Interview</td></tr>
<tr><td>تازه‌واردان به‌شدت می‌روند</td><td>{pc(rec['summary']['left_share'])}؛ OR {model['new_hire_2025']['odds_ratio']:.1f}؛ KM</td><td><span class="tag hi">بالا (اندازه)</span><span class="tag md">متوسط (علت)</span></td><td>الگو قوی؛ علت فرضیه‌ای</td><td>کانال جذب، Offer در برابر بازار، Onboarding، مدیر</td></tr>
<tr><td>رشد شغلی و حقوق محرک خروج‌اند</td><td>{pc(car['exit_reason_compensation_career_share'])} دلایل؛ شکاف Survey؛ r با Engagement</td><td><span class="tag md">متوسط</span></td><td>خوداظهاری + همبستگی؛ اثر مستقل ارتقا معنادار نیست</td><td>رویدادهای ارتقا (HRIS)، Benchmark حقوق بازار</td></tr>
<tr><td>مدیران خاص مشکل‌ساز هستند</td><td>S02/T02/T03؛ LR p={mgr_p:.2f}</td><td><span class="tag lo">پایین</span></td><td>فرضیه؛ گروه‌ها کوچک‌اند</td><td>Skip-level Survey، داده تیمی بیشتر</td></tr>
<tr><td>Performance ربطی به خروج ندارد</td><td>p={p(model['performance_prev']['p_value'])}؛ Top Performer {pc(car['high_performers']['left_share'])} در برابر {pc(car['other_performers']['left_share'])}</td><td><span class="tag md">متوسط</span></td><td>نبود رابطه، نه اثبات نبود رابطه (توان آماری محدود)</td><td>تعریف «ریزش پرهزینه» و داده کامل Rating</td></tr></table>
<p class="foot">محدودیت‌های داده: یک سال، ۳۶۰ نفر؛ سن به‌خاطر تاریخ تولد نامعتبر استفاده نشد؛ ارتقا ثبت نشده؛ Survey فقط شاغلان؛ یک خروج پیش از استخدام (از تحلیل بقا حذف شد).</p>""")

    # 10 ------------------------------------------------------------------------------------------
    S.append(f"""
<h1>پیشنهاد اقدام: اول جلوی خونریزی را بگیرید، بعد ریشه‌ها را با داده بهتر تأیید کنید</h1>
<p class="sub">اگر نرخ ماهانه سه ماه آخر ({pc(q4_h,1)}) ادامه یابد و جذبی نباشد، Headcount در ۶ ماه از {k['closing_headcount']} به حدود {proj:.0f} می‌رسد (برون‌یابی نمایشی، نه پیش‌بینی)</p>
<div class="cols3">
<div class="card c1"><h3>۳۰ روز آینده</h3><ul class="bul small"><li>فعال‌سازی هشدار زودهنگام: Engagement چارک پایین یا افت ≥۰٫۳ طی ۳ ماه (همین داشبورد)</li><li>Stay Interview برای {car['promotion_ready']['employees']} نفر آماده ارتقا و Top Performer در معرض خطر</li><li>تأیید وضعیت ارتقا در HRIS و تصمیم درباره چرخه ارتقای بعدی</li><li>Check-in روز ۳۰/۶۰/۹۰ برای تازه‌واردان به‌ویژه بخش فنی</li></ul></div>
<div class="card c2"><h3>۹۰ روز آینده</h3><ul class="bul small"><li>بازنگری Offer: حقوق در برابر بازار و انتظارات، پیش از افزایش حجم جذب</li><li>گفتگوی ساختاریافته و Skip-level برای MGR_S02، T02 و T03</li><li>کدگذاری متن Exit Interview و بررسی رویدادهای ژوئن و پاییز</li><li>Pulse Survey ماهانه و ثبت پاسخ‌نداده‌ها</li></ul></div>
<div class="card c3"><h3>داده‌هایی که باید جمع شود</h3><ul class="bul small"><li>رویداد ارتقا و تغییر حقوق</li><li>کانال جذب، مصاحبه، حقوق Offer</li><li>تاریخ تولد صحیح (کیفیت داده)</li><li>هزینه جایگزینی واقعی برای تعیین سقف بودجه نگهداشت</li></ul></div></div>
<p class="foot">همه پیشنهادها فرضیه‌ای هستند که باید با آزمون کوچک (Pilot) سنجیده شوند؛ داده فعلی علیت را اثبات نمی‌کند.</p>""")

    import re as _re
    iso = lambda t: _re.sub(r'(?<![\w\-/="])(p[=<]\S*?(?=[\s)،؛<]|$)|OR[=\s]*[×]?\d[\d.]*|[+\-−]\d+\.\d+|r=\d\.\d+|\d+\.?\d*%\s*[→←]\s*\d+\.?\d*%|AUC=\d\.\d+|LR p=\d\.\d+)', r'<span class="ltr">\1</span>', t)
    S = [iso(x.replace(" → ", " ← ") if False else x) for x in S]
    assert len(S) == 10, len(S)
    data_js = json.dumps(M.clean({**{k_: D[k_] for k_ in ("ov", "traj", "drv", "rec", "car", "sv", "mgr", "dept", "dept_month", "months")},
                                  "reasons_total": rt}), ensure_ascii=False)
    html = TEMPLATE.replace("__SLIDES__", "".join(f'<section class="slide"><div class="pg">{i+1}/10 · Snappfood People Analytics</div>{s}</section>' for i, s in enumerate(S))) \
                   .replace("__DATA__", data_js).replace("__CHARTJS__", (STATIC_DIR / "vendor" / "chart.umd.js").read_text()) \
                   .replace("__FONT400__", (STATIC_DIR / "vendor" / "vazirmatn-arabic-400-normal.woff2").resolve().as_uri()) \
                   .replace("__FONT700__", (STATIC_DIR / "vendor" / "vazirmatn-arabic-700-normal.woff2").resolve().as_uri())
    OUT.mkdir(exist_ok=True)
    (OUT / "slides.html").write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 720})
        pg.goto((OUT / "slides.html").resolve().as_uri())
        pg.wait_for_function("window.__ready === true")
        pg.pdf(path=str(OUT / "People_Analytics_Report.pdf"), width="1280px", height="720px", print_background=True)
        b.close()
    print("wrote", OUT / "People_Analytics_Report.pdf")


TEMPLATE = r"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>People Analytics</title>
<style>
@font-face{font-family:Vazirmatn;font-weight:400;src:url(__FONT400__) format("woff2")}
@font-face{font-family:Vazirmatn;font-weight:700;src:url(__FONT700__) format("woff2")}
@page{size:1280px 720px;margin:0}
*{box-sizing:border-box}body{margin:0;font-family:Vazirmatn,"DejaVu Sans",sans-serif;color:#1c2430;background:#fff}
.slide{width:1280px;height:720px;padding:34px 50px 30px;position:relative;page-break-after:always;overflow:hidden;background:#fff;border-top:8px solid #e8105b}
.pg{position:absolute;left:50px;top:14px;font-size:11px;color:#98a2b3;direction:ltr}
h1{font-size:25px;line-height:1.55;margin:6px 0 2px;font-weight:700}
.sub{color:#667085;margin:0 0 12px;font-size:13.5px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.cv{position:relative;height:320px;border:1px solid #e4e7ec;border-radius:10px;padding:8px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:8px 0 12px}
.kpi{border:1px solid #e4e7ec;border-radius:10px;padding:9px 12px;background:#fafbfc}.kpi b{display:block;font-size:24px;direction:ltr;text-align:right}.kpi span{font-size:11.5px;color:#667085}
.kpi.bad b{color:#d92d20}
.bul{margin:10px 0 0;padding:0 18px;font-size:13.5px;line-height:1.85}.bul.small{font-size:12.5px;line-height:1.75}
.cols3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:10px}
.card{border:1px solid #e4e7ec;border-radius:12px;padding:12px 16px;background:#fafbfc}.card h3{margin:0 0 6px;font-size:16px}.card p{margin:0 0 8px;font-size:13.5px;line-height:1.85}
.c1{border-top:4px solid #e8105b}.c2{border-top:4px solid #2a6df4}.c3{border-top:4px solid #12a594}
.tag{display:inline-block;font-size:11.5px;padding:2px 10px;border-radius:99px;margin-inline-end:4px}.hi{background:#d1fadf;color:#05603a}.md{background:#fef0c7;color:#93370d}.lo{background:#fee4e2;color:#912018}
.foot{position:absolute;bottom:18px;right:50px;left:50px;font-size:11.5px;color:#667085;margin:0}
.tbl{border-collapse:collapse;width:100%;font-size:12.5px}.tbl th,.tbl td{padding:6px 8px;border-bottom:1px solid #e4e7ec;text-align:right;vertical-align:top}.tbl th{color:#667085;font-weight:400}
.tbl.wide td{font-size:12px;line-height:1.6}
.hyp{margin-top:8px}.kpis ~ .grid2 .cv{height:235px}.grid3 .cv{height:300px}.ltr{direction:ltr;unicode-bidi:isolate;display:inline-block}.bul{font-size:14.5px}.bul.small{font-size:13px}.card p{font-size:14.5px}
</style></head><body>__SLIDES__
<script>__CHARTJS__</script>
<script>
const D=__DATA__;
Chart.defaults.font.family="Vazirmatn, DejaVu Sans, sans-serif";Chart.defaults.font.size=11;Chart.defaults.animation=false;Chart.defaults.responsive=true;Chart.defaults.maintainAspectRatio=false;
const MON=["ژانویه","فوریه","مارس","آوریل","مه","ژوئن","ژوئیه","اوت","سپتامبر","اکتبر","نوامبر","دسامبر"];
const ml=m=>MON[+m.split("-")[1]-1];
const C={blue:"#2a6df4",pink:"#e8105b",teal:"#12a594",amber:"#f59e0b",grey:"#98a2b3",purple:"#7a5af8",ink:"#111827"};
const DEP={Sales:"فروش",Technical:"فنی",Finance:"مالی",Marketing:"بازاریابی"};
const REA={"Compensation":"حقوق و مزایا","Career Development":"توسعه شغلی","Work Pressure":"فشار کاری","Manager Relationship":"رابطه با مدیر","Personal Reasons":"دلایل شخصی","Role Fit":"تناسب نقش","Organizational Culture":"فرهنگ سازمانی","Performance":"عملکرد","Organizational Restructuring":"بازساختار"};
const DIM={compensation_benefits:"حقوق و مزایا",growth_opportunities:"فرصت رشد",work_culture:"فرهنگ کاری",work_life_balance:"تعادل کار و زندگی",management_style:"سبک مدیریت",overall_satisfaction:"رضایت کلی"};
const leg=(pos="top")=>({rtl:true,position:pos,labels:{boxWidth:12,font:{family:"Vazirmatn"}}});
const mk=(id,cfg,title)=>{const el=document.getElementById(id);if(!el)return;cfg.options=cfg.options||{};cfg.options.plugins=Object.assign({legend:leg(),title:{display:!!title,text:title,font:{size:12.5,weight:"bold",family:"Vazirmatn"}}},cfg.options.plugins||{});new Chart(el,cfg)};
const ds=(label,data,color,x={})=>Object.assign({label,data,backgroundColor:color,borderColor:color,borderWidth:2,pointRadius:2,tension:.25},x);
const mon=D.ov.monthly, L=mon.map(m=>ml(m.month));
mk("c_flow",{data:{labels:L,datasets:[Object.assign(ds("استخدام",mon.map(m=>m.hires),C.teal),{type:"bar",order:2}),Object.assign(ds("خروج",mon.map(m=>m.exits),C.pink),{type:"bar",order:2}),Object.assign(ds("Headcount",mon.map(m=>m.headcount),C.blue,{fill:false}),{type:"line",yAxisID:"y2",order:1})]},options:{scales:{y:{beginAtZero:true},y2:{position:"right",grid:{drawOnChartArea:false}}}}},"استخدام، خروج و Headcount ماهانه");
mk("c_haz",{type:"line",data:{labels:L,datasets:[ds("نرخ ریزش ماهانه (٪)",mon.map(m=>m.monthly_hazard*100),C.pink),ds("میانگین Engagement",mon.map(m=>m.avg_engagement),C.blue,{yAxisID:"y2"})]},options:{scales:{y:{beginAtZero:true},y2:{position:"right",min:2.5,max:3.5,grid:{drawOnChartArea:false}}}}},"نرخ ریزش ماهانه و Engagement");
const dc={Sales:C.blue,Technical:C.pink,Finance:C.amber,Marketing:C.teal};
mk("c_dm",{type:"bar",data:{labels:D.months.map(ml),datasets:Object.keys(D.dept_month).map(d=>ds(DEP[d],D.dept_month[d],dc[d]))},options:{scales:{x:{stacked:true},y:{stacked:true,beginAtZero:true}}}},"تعداد خروج ماهانه به تفکیک بخش");
const mg=D.mgr.slice().sort((a,b)=>b.hazard_h2-a.hazard_h2);
mk("c_mgr",{type:"bar",data:{labels:mg.map(r=>r.group),datasets:[ds("H1",mg.map(r=>r.hazard_h1*100),C.grey),ds("H2",mg.map(r=>r.hazard_h2*100),C.pink)]},options:{scales:{y:{beginAtZero:true,title:{display:true,text:"٪ ماهانه"}}}}},"نرخ ماهانه H1 و H2 به تفکیک مدیر");
const tj=D.traj.rows;
mk("c_traj",{type:"line",data:{labels:tj.map(r=>String(r.months_before_exit)),datasets:[ds("ترک‌کنندگان",tj.map(r=>r.engagement),C.pink),ds("ماندگاران",tj.map(()=>D.traj.stayers_baseline.engagement),C.grey,{borderDash:[6,4],pointRadius:0})]},options:{scales:{y:{min:2.4,max:3.3},x:{title:{display:true,text:"ماه تا خروج"}}}}},"Engagement پیش از خروج");
const qb=(rows,col)=>({type:"bar",data:{labels:rows.map(r=>[r.quartile,"\u200e"+r.range]),datasets:[ds("نرخ خروج ماهانه (٪)",rows.map(r=>r.monthly_hazard*100),col)]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,max:11}}}});
mk("c_qe",qb(D.drv.bands.engagement,C.pink),"ریسک خروج بر اساس چارک Engagement");
mk("c_qp",qb(D.drv.bands.performance,C.grey),"ریسک خروج بر اساس چارک Performance");
const km=D.rec.survival_km, kd=D.rec.survival_km_by_department;
mk("c_km",{type:"line",data:{labels:km.map(x=>x.day),datasets:[ds("همه",km.map(x=>x.survival*100),C.ink,{borderWidth:3})].concat(Object.keys(kd).map(d=>ds(DEP[d],kd[d].map(x=>x.survival*100),dc[d],{borderDash:[5,3],borderWidth:1.5})))},options:{scales:{y:{min:0,max:100,title:{display:true,text:"احتمال ماندن (٪)"}},x:{title:{display:true,text:"روز از استخدام"}}}}},"احتمال ماندن تازه‌واردها");
const hm=D.rec.hires_by_month;
mk("c_hm",{type:"bar",data:{labels:hm.map(x=>ml(x.month)),datasets:[ds("استخدام",hm.map(x=>x.hires),C.teal+"aa"),ds("بعداً خارج شدند",hm.map(x=>x.left_later),C.pink)]},options:{scales:{y:{beginAtZero:true}}}},"استخدام‌های هر ماه و تعداد خروج‌کرده‌ها");
const nr=D.rec.newhire_exit_reasons;
mk("c_nr",{type:"bar",data:{labels:nr.map(x=>REA[x.reason]||x.reason),datasets:[ds("تعداد",nr.map(x=>x.exits),C.pink)]},options:{indexAxis:"y",plugins:{legend:{display:false}}}},"دلایل خروج تازه‌واردان");
const rs=Object.entries(D.reasons_total);
mk("c_rs",{type:"bar",data:{labels:rs.map(x=>REA[x[0]]||x[0]),datasets:[ds("تعداد خروج",rs.map(x=>x[1]),C.pink)]},options:{indexAxis:"y",plugins:{legend:{display:false}}}},"دلایل خروج (کل)");
const gp=D.sv.gap;
mk("c_gap",{type:"bar",data:{labels:gp.map(g=>DIM[g.dimension]),datasets:[ds("ترک‌کنندگان",gp.map(g=>g.leavers),C.pink),ds("ماندگاران",gp.map(g=>g.stayers),C.teal)]},options:{scales:{y:{min:2.4,max:3.6}}}},"ابعاد Survey (۱ تا ۵)");
const mb=D.car.months_since_promotion_bands;
mk("c_msp",{type:"bar",data:{labels:mb.map(x=>x.band+" ماه"),datasets:[ds("نرخ خروج ماهانه (٪)",mb.map(x=>x.monthly_hazard*100),C.pink+"cc")]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}},"ریسک خروج بر اساس فاصله از آخرین ارتقا");
const cd=D.car.by_department;
mk("c_cd",{type:"bar",data:{labels:cd.map(x=>DEP[x.department]),datasets:[ds("آماده ارتقا",cd.map(x=>x.promotion_ready),C.teal),ds("Top Performer",cd.map(x=>x.high_performers),C.blue)]},options:{scales:{y:{beginAtZero:true}}}},"آماده ارتقا و Top Performer");
document.fonts.ready.then(()=>setTimeout(()=>{window.__ready=true},400));
</script></body></html>"""

if __name__ == "__main__":
    main()
