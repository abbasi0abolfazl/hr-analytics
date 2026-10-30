/* People Analytics dashboard – talks to the FastAPI service over HTTP only.
   Every filter change issues new GET requests (see the request log in the footer). */
(() => {
const FA = {
  title:"داشبورد تحلیل منابع انسانی", tab_overview:"نمای کلی", tab_attrition:"ریزش (Attrition)", tab_signals:"سیگنال‌های ریسک",
  tab_engagement:"Engagement Survey", tab_recruitment:"جذب و تازه‌واردها", tab_careers:"رشد شغلی", tab_dq:"کیفیت داده",
  f_dept:"بخش", f_manager:"مدیر", f_type:"نوع استخدام", f_loc:"محل کار", f_grade:"گرید حقوقی", f_from:"از ماه", f_to:"تا ماه",
  reset:"بازنشانی", all:"همه", by:"تفکیک بر اساس", driver:"متغیر", req:"آخرین درخواست‌های API:",
  c_flow:"ورودی و خروجی ماهانه و Headcount", c_hazard:"نرخ ریزش ماهانه در برابر Engagement",
  n_hazard:"نرخ ریزش = خروج‌ها ÷ افراد شاغل در همان ماه. میانگین Engagement مقیاس ۱ تا ۵ است.",
  c_turnover:"نرخ ریزش سالانه‌شده و نرخ ماهانه نیمه اول/دوم", n_bd:"نوار بالا: ریزش سالانه‌شده؛ خطوط: نرخ ماهانه H1 و H2. گروه‌های کوچک عدم قطعیت بالایی دارند (جدول زیر بازه اطمینان دارد).",
  c_reasons:"دلایل خروج", c_table:"جزئیات",
  c_traj:"مسیر قبل از خروج: Engagement", n_traj:"میانگین Engagement ترک‌کنندگان k ماه پیش از خروج، در مقایسه با میانگین کسانی که نرفته‌اند.",
  c_quart:"نرخ خروج ماهانه به تفکیک چارک (ماه قبل)", c_model:"مدل لجستیک: نسبت بخت (Odds Ratio)",
  n_model:"OR کمتر از ۱ یعنی ریسک خروج کمتر. این مدل همبستگیِ تعدیل‌شده را نشان می‌دهد و علیت را اثبات نمی‌کند.",
  c_gap:"امتیاز ابعاد Survey: ترک‌کنندگان در برابر ماندگاران (۱ تا ۵)", c_dimq:"روند فصلی ابعاد",
  c_cov:"پوشش پاسخ و Recommend (٪ مطلوب ۴–۵؛ نه eNPS)", n_cov:"فقط افرادِ شاغل در زمان Survey حضور دارند؛ نتایج دچار survivorship bias هستند.",
  c_km:"احتمال ماندن تازه‌واردها (Kaplan–Meier)", n_km:"KM با لحاظ censoring: افراد استخدام‌شده در اواخر سال هنوز فرصت کافی برای خروج نداشته‌اند.",
  c_hm:"استخدام ماهانه و تعداد خروج‌کرده‌ها از همان گروه", c_rdept:"به تفکیک بخش",
  c_msp:"نرخ خروج ماهانه بر اساس ماه‌های گذشته از آخرین ارتقا", c_cdept:"آماده ارتقا و Top Performer به تفکیک بخش",
  c_dq:"ثبت مسائل کیفیت داده و تصمیم‌ها",
  empty:"داده‌ای با این فیلترها پیدا نشد. فیلترها را کم‌تر محدود کنید.", err:"خطا در دریافت داده",
  hires:"استخدام", exits:"خروج", headcount:"Headcount", hazard:"نرخ ریزش ماهانه", engagement:"Engagement", performance:"Performance", skills_gap:"Skills Gap",
  months_since_promotion:"ماه از آخرین ارتقا",
  k_open:"Headcount ابتدای سال", k_close:"Headcount پایان سال", k_net:"تغییر خالص", k_hires:"استخدام‌ها", k_exits:"خروج‌ها",
  k_turn:"ریزش سالانه‌شده", k_h1:"نرخ ماهانه H1", k_h2:"نرخ ماهانه H2", k_eng:"میانگین Engagement", k_vol:"خروج داوطلبانه",
  group:"گروه", emp:"نفر", pm:"نفر-ماه", annual:"ریزش سالانه", ci:"بازه اطمینان ماهانه ۹۵٪", h1:"H1", h2:"H2",
  voluntary:"داوطلبانه", involuntary:"غیرداوطلبانه", stayers:"ماندگاران", leavers:"ترک‌کنندگان", months_before:"ماه تا خروج",
  term:"متغیر", or:"OR", p:"p-value", auc:"AUC (فقط Engagement)", mgr_eff:"اثر مدیر (LR test)", model_na:"مدل در دسترس نیست",
  quarter:"فصل", resp:"پاسخ", employed:"شاغل در ماه", coverage:"پوشش", fav:"٪ مطلوب Recommend",
  k_req:"درخواست‌های جذب", k_acc:"نرخ پذیرش Offer", k_hired:"استخدام‌شده", k_left:"خروج در همان سال", k_leftp:"٪ خروج", k_med:"میانه روز تا خروج",
  k_cost:"میانگین هزینه هر استخدام", k_sunk:"هزینه استخدام‌های ازدست‌رفته", k_dtf:"میانگین Days to Fill (استخدام‌شده)", k_90:"خروج ≤ ۹۰ روز",
  survival:"احتمال ماندن", day:"روز", later_left:"بعداً خارج شد",
  c_promo_events:"ارتقاهای ثبت‌شده", c_pr:"آماده ارتقا", c_pr_left:"٪ خروج آماده‌ارتقاها", c_hp:"Top Performer (≥۴)", c_hp_left:"٪ خروج Top Performerها",
  c_cc:"سهم دلایل حقوق + رشد شغلی", c_rehire:"قابل بازگشت (Top Performer رفته)", promo_ready:"آماده ارتقا", high_perf:"Top Performer",
  severity:"شدت", table:"جدول", rows:"تعداد", issue:"مسئله", decision:"تصمیم", imported:"آخرین Import",
  q:{Q1:"چارک ۱ (کمترین)",Q2:"چارک ۲",Q3:"چارک ۳",Q4:"چارک ۴ (بیشترین)"},
  bd:{department:"بخش",manager_id:"مدیر",employment_type:"نوع استخدام",work_location:"محل کار",salary_grade:"گرید",tenure_band:"سابقه (ماه)",hire_cohort:"گروه استخدام"},
  drv:{engagement:"Engagement",performance:"Performance",skills_gap:"Skills Gap",months_since_promotion:"ماه از آخرین ارتقا"},
  dim:{compensation_benefits:"حقوق و مزایا",growth_opportunities:"فرصت رشد",work_culture:"فرهنگ کاری",work_life_balance:"تعادل کار و زندگی",management_style:"سبک مدیریت",overall_satisfaction:"رضایت کلی",recommend_to_friend:"Recommend"},
  reason:{"Compensation":"حقوق و مزایا","Career Development":"توسعه شغلی","Work Pressure":"فشار کاری","Manager Relationship":"رابطه با مدیر","Personal Reasons":"دلایل شخصی","Role Fit":"تناسب نقش","Organizational Culture":"فرهنگ سازمانی","Performance":"عملکرد","Organizational Restructuring":"بازساختار"},
  dept:{Sales:"فروش",Finance:"مالی",Marketing:"بازاریابی",Technical:"فنی"},
  coh:{new_hire_2025:"استخدام ۲۰۲۵",existing:"قبلی"},
  mon:["ژانویه","فوریه","مارس","آوریل","مه","ژوئن","ژوئیه","اوت","سپتامبر","اکتبر","نوامبر","دسامبر"]
};
const EN = {
  title:"HR People Analytics Dashboard", tab_overview:"Overview", tab_attrition:"Attrition", tab_signals:"Risk signals",
  tab_engagement:"Engagement Survey", tab_recruitment:"Hiring & new joiners", tab_careers:"Careers", tab_dq:"Data quality",
  f_dept:"Department", f_manager:"Manager", f_type:"Employment type", f_loc:"Work location", f_grade:"Salary grade", f_from:"From month", f_to:"To month",
  reset:"Reset", all:"All", by:"Break down by", driver:"Variable", req:"Latest API requests:",
  c_flow:"Monthly hires, exits and headcount", c_hazard:"Monthly attrition rate vs. engagement",
  n_hazard:"Attrition rate = exits ÷ employees employed that month. Engagement is on a 1–5 scale.",
  c_turnover:"Annualised turnover and monthly rate in H1 / H2", n_bd:"Bars: annualised turnover; lines: monthly rate in H1 and H2. Small groups are noisy (95% CI in the table).",
  c_reasons:"Exit reasons", c_table:"Details",
  c_traj:"Pre-exit trajectory: engagement", n_traj:"Mean engagement of leavers k months before exit vs. employees who never left.",
  c_quart:"Monthly exit rate by quartile (previous month)", c_model:"Logistic model: odds ratios",
  n_model:"OR below 1 = lower exit risk. Adjusted association only – not proof of causation.",
  c_gap:"Survey dimensions: leavers vs. stayers (1–5)", c_dimq:"Quarterly trend by dimension",
  c_cov:"Response coverage & Recommend (% favourable 4–5, not eNPS)", n_cov:"Only people still employed at survey time appear – survivorship bias applies.",
  c_km:"New-hire retention (Kaplan–Meier)", n_km:"KM handles censoring: late-year hires have had less time to leave.",
  c_hm:"Hires per month and how many of them later left", c_rdept:"By department",
  c_msp:"Monthly exit rate by months since last promotion", c_cdept:"Promotion-ready and top performers by department",
  c_dq:"Data-quality register and decisions",
  empty:"No data matches these filters. Try relaxing them.", err:"Error fetching data",
  hires:"Hires", exits:"Exits", headcount:"Headcount", hazard:"Monthly attrition rate", engagement:"Engagement", performance:"Performance", skills_gap:"Skills Gap",
  months_since_promotion:"Months since last promotion",
  k_open:"Opening headcount", k_close:"Closing headcount", k_net:"Net change", k_hires:"Hires", k_exits:"Exits",
  k_turn:"Annualised turnover", k_h1:"Monthly rate H1", k_h2:"Monthly rate H2", k_eng:"Avg engagement", k_vol:"Voluntary exits",
  group:"Group", emp:"Employees", pm:"Person-months", annual:"Annual turnover", ci:"95% CI (monthly)", h1:"H1", h2:"H2",
  voluntary:"Voluntary", involuntary:"Involuntary", stayers:"Stayers", leavers:"Leavers", months_before:"Months before exit",
  term:"Term", or:"OR", p:"p-value", auc:"AUC (engagement only)", mgr_eff:"Manager effect (LR test)", model_na:"Model not available",
  quarter:"Quarter", resp:"Responses", employed:"Employed in month", coverage:"Coverage", fav:"% favourable Recommend",
  k_req:"Requisitions", k_acc:"Offer acceptance", k_hired:"Hired", k_left:"Left within the year", k_leftp:"% left", k_med:"Median days to exit",
  k_cost:"Avg cost per hire", k_sunk:"Cost of hires who left", k_dtf:"Avg days to fill (hired)", k_90:"Left ≤ 90 days",
  survival:"Survival", day:"Day", later_left:"Later left",
  c_promo_events:"Promotions recorded", c_pr:"Promotion-ready", c_pr_left:"% of promotion-ready who left", c_hp:"Top performers (≥4)", c_hp_left:"% of top performers who left",
  c_cc:"Share of exits: pay + career", c_rehire:"Rehire-eligible (top performers who left)", promo_ready:"Promotion-ready", high_perf:"Top performers",
  severity:"Severity", table:"Table", rows:"Rows", issue:"Issue", decision:"Decision", imported:"Last import",
  q:{Q1:"Q1 (lowest)",Q2:"Q2",Q3:"Q3",Q4:"Q4 (highest)"},
  bd:{department:"Department",manager_id:"Manager",employment_type:"Employment type",work_location:"Work location",salary_grade:"Salary grade",tenure_band:"Tenure (months)",hire_cohort:"Hire cohort"},
  drv:{engagement:"Engagement",performance:"Performance",skills_gap:"Skills Gap",months_since_promotion:"Months since last promotion"},
  dim:{compensation_benefits:"Compensation & benefits",growth_opportunities:"Growth opportunities",work_culture:"Work culture",work_life_balance:"Work-life balance",management_style:"Management style",overall_satisfaction:"Overall satisfaction",recommend_to_friend:"Recommend"},
  reason:{}, dept:{}, coh:{new_hire_2025:"2025 hires",existing:"Existing"},
  mon:["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
};
const TR = {fa: FA, en: EN};
let lang = localStorage.getItem("lang") || "fa";
const T = () => TR[lang];
const tr = (grp, k) => (T()[grp] && T()[grp][k]) || k;
const $ = (s, r = document) => r.querySelector(s);
const pct = (v, d = 1) => v == null ? "–" : (v * 100).toFixed(d) + "%";
const num = (v, d = 0) => v == null ? "–" : Number(v).toLocaleString("en-US", {maximumFractionDigits: d});
const monthLabel = m => { const [y, mm] = m.split("-"); return T().mon[+mm - 1] + " " + y.slice(2); };
const C = {blue:"#2a6df4", pink:"#e8105b", teal:"#12a594", amber:"#f59e0b", grey:"#98a2b3", red:"#d92d20", purple:"#7a5af8"};

const state = {tab:"overview", f:{department:new Set(), manager_id:new Set(), employment_type:"", work_location:"", salary_grade:"", month_from:"", month_to:""}, meta:null};
const charts = {};
const reqlog = [];

function qs(extra = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(state.f)) {
    if (v instanceof Set) v.forEach(x => p.append(k, x)); else if (v) p.set(k, v);
  }
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p.toString();
}
async function api(path, extra = {}, useFilters = true) {
  const q = useFilters ? qs(extra) : new URLSearchParams(extra).toString();
  const url = q ? path + "?" + q : path;
  let status = 0;
  try {
    const r = await fetch(url); status = r.status;
    const j = await r.json();
    reqlog.unshift(`${status} ${url}`); reqlog.length = Math.min(reqlog.length, 3); $("#reqlog").textContent = reqlog.join("  |  ");
    if (!r.ok) { banner((j.error && j.error.message) || T().err, true); return null; }
    if (j.meta && j.meta.empty) banner(T().empty, false); 
    return j.data;
  } catch (e) { banner(T().err + ": " + e.message, true); return null; }
}
function banner(msg, err) { const b = $("#banner"); b.hidden = !msg; b.textContent = msg || ""; b.className = "banner" + (err ? " err" : ""); }

function mk(id, cfg) {
  if (charts[id]) charts[id].destroy();
  const rtl = lang === "fa";
  cfg.options = Object.assign({responsive:true, maintainAspectRatio:false, animation:false}, cfg.options || {});
  cfg.options.plugins = Object.assign({legend:{rtl, labels:{font:{family:"Vazirmatn"}}}, tooltip:{rtl, bodyFont:{family:"Vazirmatn"}}}, cfg.options.plugins || {});
  charts[id] = new Chart($("#" + id), cfg);
}
const clear = id => { if (charts[id]) { charts[id].destroy(); delete charts[id]; } };
const ds = (label, data, color, extra = {}) => Object.assign({label, data, backgroundColor:color, borderColor:color, borderWidth:2, pointRadius:2, tension:.25}, extra);
const kpi = (l, v, cls = "") => `<div class="kpi ${cls}"><div class="v">${v}</div><div class="l">${l}</div></div>`;

// ------------------------------------------------------------------ tabs
const loaders = {
  async overview() {
    const d = await api("/api/overview");
    if (!d || d.empty) { $("#kpis").innerHTML = ""; clear("ch-flow"); clear("ch-hazard"); return; }
    const k = d.kpi, t = T();
    $("#kpis").innerHTML = kpi(t.k_open, num(k.opening_headcount)) + kpi(t.k_close, num(k.closing_headcount)) +
      kpi(t.k_net, pct(k.net_change_pct), k.net_change_pct < 0 ? "bad" : "good") + kpi(t.k_hires, num(k.hires)) +
      kpi(t.k_exits, num(k.exits), "bad") + kpi(t.k_vol, num(k.voluntary_exits)) + kpi(t.k_turn, pct(k.annualized_turnover, 0), "bad") +
      kpi(t.k_h1, pct(k.hazard_h1)) + kpi(t.k_h2, pct(k.hazard_h2), k.hazard_h2 > (k.hazard_h1 || 0) * 1.5 ? "bad" : "") + kpi(t.k_eng, num(k.avg_engagement, 2));
    const L = d.monthly.map(m => monthLabel(m.month));
    mk("ch-flow", {data:{labels:L, datasets:[
      Object.assign(ds(t.hires, d.monthly.map(m => m.hires), C.teal), {type:"bar", order:2}),
      Object.assign(ds(t.exits, d.monthly.map(m => m.exits), C.pink), {type:"bar", order:2}),
      Object.assign(ds(t.headcount, d.monthly.map(m => m.headcount), C.blue, {fill:false}), {type:"line", yAxisID:"y2", order:1})]},
      options:{scales:{y:{beginAtZero:true}, y2:{position:"right", grid:{drawOnChartArea:false}}}}});
    mk("ch-hazard", {type:"line", data:{labels:L, datasets:[
      ds(t.hazard + " (%)", d.monthly.map(m => m.monthly_hazard * 100), C.pink),
      ds(t.engagement, d.monthly.map(m => m.avg_engagement), C.blue, {yAxisID:"y2"})]},
      options:{scales:{y:{beginAtZero:true, title:{display:true, text:"%"}}, y2:{position:"right", min:2.5, max:3.5, grid:{drawOnChartArea:false}}}}});
  },
  async attrition() {
    const by = $("#by").value || "department";
    const [b, r] = await Promise.all([api("/api/attrition/breakdown", {by}), api("/api/attrition/reasons")]);
    const t = T();
    if (!b || b.empty) { clear("ch-bd"); $("#bd-table").innerHTML = ""; } else {
      const lab = x => by === "department" ? tr("dept", x) : by === "hire_cohort" ? tr("coh", x) : x;
      mk("ch-bd", {data:{labels:b.rows.map(x => lab(x.group)), datasets:[
        Object.assign(ds(t.annual + " (%)", b.rows.map(x => x.annualized_turnover * 100), C.pink + "cc"), {type:"bar", yAxisID:"y"}),
        Object.assign(ds(t.h1 + " (% / mo)", b.rows.map(x => x.hazard_h1 == null ? null : x.hazard_h1 * 100), C.grey, {showLine:false, pointRadius:6}), {type:"line", yAxisID:"y2"}),
        Object.assign(ds(t.h2 + " (% / mo)", b.rows.map(x => x.hazard_h2 == null ? null : x.hazard_h2 * 100), C.blue, {showLine:false, pointStyle:"rectRot", pointRadius:7}), {type:"line", yAxisID:"y2"})]},
        options:{scales:{y:{beginAtZero:true}, y2:{position:"right", beginAtZero:true, grid:{drawOnChartArea:false}}}}});
      $("#bd-table").innerHTML = `<table><tr><th>${t.group}</th><th class=n>${t.emp}</th><th class=n>${t.pm}</th><th class=n>${t.exits}</th><th class=n>${t.annual}</th><th class=n>${t.h1}</th><th class=n>${t.h2}</th><th class=n>${t.ci}</th><th class=n>${t.engagement}</th></tr>` +
        b.rows.map(x => `<tr><td>${lab(x.group)}</td><td class=n>${x.n_employees}</td><td class=n>${x.person_months}</td><td class=n>${x.exits}</td><td class=n>${pct(x.annualized_turnover, 0)}</td><td class=n>${pct(x.hazard_h1)}</td><td class=n>${pct(x.hazard_h2)}</td><td class=n>${pct(x.hazard_ci_low)}–${pct(x.hazard_ci_high)}</td><td class=n>${num(x.avg_engagement, 2)}</td></tr>`).join("") + "</table>";
    }
    if (!r || r.empty) clear("ch-reasons"); else {
      const names = [...new Set(r.rows.map(x => x.reason))];
      const tot = n => r.rows.filter(x => x.reason === n).reduce((a, x) => a + x.exits, 0);
      names.sort((a, c) => tot(c) - tot(a));
      const get = (n, ty) => (r.rows.find(x => x.reason === n && x.exit_type === ty) || {exits:0}).exits;
      mk("ch-reasons", {type:"bar", data:{labels:names.map(n => tr("reason", n)), datasets:[
        ds(t.voluntary, names.map(n => get(n, "Voluntary")), C.blue), ds(t.involuntary, names.map(n => get(n, "Involuntary")), C.grey)]},
        options:{indexAxis:"y", scales:{x:{stacked:true}, y:{stacked:true}}}});
    }
  },
  async signals() {
    const drv = $("#driver").value || "engagement";
    const [tj, dr] = await Promise.all([api("/api/signals/trajectory"), api("/api/signals/drivers")]);
    const t = T();
    if (!tj || tj.empty) clear("ch-traj"); else {
      mk("ch-traj", {type:"line", data:{labels:tj.rows.map(x => String(x.months_before_exit)), datasets:[
        ds(t.leavers, tj.rows.map(x => x.engagement), C.pink),
        ds(t.stayers, tj.rows.map(() => tj.stayers_baseline.engagement), C.grey, {borderDash:[6, 4], pointRadius:0})]},
        options:{scales:{y:{suggestedMin:2.4, suggestedMax:3.4}, x:{title:{display:true, text:t.months_before}}}}});
    }
    if (!dr || dr.empty) { clear("ch-quart"); $("#model").innerHTML = ""; return; }
    const rows = dr.bands[drv] || [];
    mk("ch-quart", {type:"bar", data:{labels:rows.map(x => [tr("q", x.quartile), "\u200e" + x.range]), datasets:[ds(t.hazard + " (%)", rows.map(x => x.monthly_hazard * 100), C.pink + "cc")]},
      options:{plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true, title:{display:true, text:"%"}}}}});
    const m = dr.model;
    if (!m.available) { $("#model").innerHTML = `<p>${t.model_na}: ${m.reason}</p>`; return; }
    $("#model").innerHTML = `<table><tr><th>${t.term}</th><th class=n>${t.or}</th><th class=n>95% CI</th><th class=n>${t.p}</th></tr>` +
      m.terms.map(x => `<tr><td>${x.term}</td><td class=n>${num(x.odds_ratio, 2)}</td><td class=n>${num(x.ci_low, 2)}–${num(x.ci_high, 2)}</td><td class="n ${x.p_value < 0.05 ? "sig" : ""}">${x.p_value < 0.001 ? "<0.001" : num(x.p_value, 3)}</td></tr>`).join("") +
      `</table><p class="note">n=${m.n_person_months} ${t.pm}, ${m.n_exits} ${t.exits} · ${t.auc}: ${num(m.auc_engagement_only, 2)}` +
      (m.manager_effect ? ` · ${t.mgr_eff}: χ²=${num(m.manager_effect.lr_chi2, 1)}, df=${m.manager_effect.df}, p=${num(m.manager_effect.p_value, 3)}` : "") + `</p>`;
  },
  async engagement() {
    const d = await api("/api/engagement/survey"), t = T();
    if (!d || d.empty) { clear("ch-gap"); clear("ch-dimq"); $("#cov").innerHTML = ""; return; }
    const dims = d.gap.map(x => x.dimension);
    mk("ch-gap", {type:"bar", data:{labels:dims.map(x => tr("dim", x)), datasets:[ds(t.leavers, d.gap.map(x => x.leavers), C.pink), ds(t.stayers, d.gap.map(x => x.stayers), C.teal)]},
      options:{scales:{y:{min:2.4, max:3.6}}}});
    const cols = [C.blue, C.pink, C.teal, C.amber, C.purple, C.grey];
    mk("ch-dimq", {type:"line", data:{labels:d.by_quarter.map(x => x.survey_quarter), datasets:dims.map((k, i) => ds(tr("dim", k), d.by_quarter.map(x => x[k]), cols[i]))},
      options:{scales:{y:{min:2.5, max:3.6}}}});
    $("#cov").innerHTML = `<table><tr><th>${t.quarter}</th><th class=n>${t.resp}</th><th class=n>${t.employed}</th><th class=n>${t.coverage}</th><th class=n>${t.fav}</th></tr>` +
      d.coverage.map(x => `<tr><td>${x.quarter}</td><td class=n>${x.responses}</td><td class=n>${x.employed_in_month}</td><td class=n>${pct(x.coverage, 0)}</td><td class=n>${pct(x.recommend_favourable_pct, 0)}</td></tr>`).join("") + "</table>";
  },
  async recruitment() {
    const d = await api("/api/recruitment"), t = T();
    if (!d || d.empty) { $("#rkpis").innerHTML = ""; clear("ch-km"); clear("ch-hm"); $("#rdept").innerHTML = ""; return; }
    const f = d.funnel, s = d.summary;
    $("#rkpis").innerHTML = kpi(t.k_req, f.requisitions) + kpi(t.k_acc, pct(f.acceptance_rate, 0)) + kpi(t.k_hired, s.hires) + kpi(t.k_left, s.left_in_year, "bad") +
      kpi(t.k_leftp, pct(s.left_share, 0), "bad") + kpi(t.k_med, num(s.median_days_to_exit)) + kpi(t.k_90, s.left_within_90d) +
      kpi(t.k_dtf, num(f.days_to_fill_hired, 1)) + kpi(t.k_cost, num(f.avg_cost_per_hire / 1e6, 1) + "M") + kpi(t.k_sunk, num((s.sunk_cost_of_leavers || 0) / 1e6, 0) + "M", "bad");
    const colors = {Finance:C.amber, Marketing:C.teal, Sales:C.blue, Technical:C.pink};
    const sets = [Object.assign(ds("All", d.survival_km.map(x => x.survival * 100), "#111827", {borderWidth:3}))];
    Object.entries(d.survival_km_by_department).forEach(([k, v]) => sets.push(ds(tr("dept", k), v.map(x => x.survival * 100), colors[k] || C.grey, {borderDash:[5, 3], borderWidth:1.5})));
    mk("ch-km", {type:"line", data:{labels:d.survival_km.map(x => x.day), datasets:sets}, options:{scales:{y:{min:0, max:100, title:{display:true, text:t.survival + " %"}}, x:{title:{display:true, text:t.day}}}}});
    mk("ch-hm", {type:"bar", data:{labels:d.hires_by_month.map(x => monthLabel(x.month)), datasets:[ds(t.hires, d.hires_by_month.map(x => x.hires), C.teal + "aa"), ds(t.later_left, d.hires_by_month.map(x => x.left_later), C.pink)]}, options:{scales:{y:{beginAtZero:true}}}});
    $("#rdept").innerHTML = `<table><tr><th>${t.f_dept}</th><th class=n>${t.k_req}</th><th class=n>${t.k_acc}</th><th class=n>${t.k_hired}</th><th class=n>${t.k_left}</th><th class=n>${t.k_leftp}</th><th class=n>${t.k_dtf}</th></tr>` +
      d.by_department.map(x => `<tr><td>${tr("dept", x.department)}</td><td class=n>${x.requisitions}</td><td class=n>${pct(x.acceptance_rate, 0)}</td><td class=n>${x.hires}</td><td class=n>${x.left_in_year}</td><td class=n>${pct(x.left_share, 0)}</td><td class=n>${num(x.days_to_fill_hired, 1)}</td></tr>`).join("") + "</table>";
  },
  async careers() {
    const d = await api("/api/careers"), t = T();
    if (!d || d.empty) { $("#ckpis").innerHTML = ""; clear("ch-msp"); clear("ch-cdept"); return; }
    $("#ckpis").innerHTML = kpi(t.c_promo_events, d.promotion_events_observed, d.promotion_events_observed === 0 ? "bad" : "") +
      kpi(t.c_pr, d.promotion_ready.employees) + kpi(t.c_pr_left, pct(d.promotion_ready.left_share, 0), "bad") +
      kpi(t.c_hp, d.high_performers.employees) + kpi(t.c_hp_left, pct(d.high_performers.left_share, 0), "bad") +
      kpi(t.c_cc, pct(d.exit_reason_compensation_career_share, 0)) + kpi(t.c_rehire, pct(d.high_performer_leavers_rehire_eligible_share, 0));
    mk("ch-msp", {type:"bar", data:{labels:d.months_since_promotion_bands.map(x => x.band), datasets:[ds(t.hazard + " (%)", d.months_since_promotion_bands.map(x => x.monthly_hazard * 100), C.pink + "cc")]},
      options:{plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}}}});
    mk("ch-cdept", {type:"bar", data:{labels:d.by_department.map(x => tr("dept", x.department)), datasets:[ds(t.promo_ready, d.by_department.map(x => x.promotion_ready), C.teal), ds(t.high_perf, d.by_department.map(x => x.high_performers), C.blue)]}, options:{scales:{y:{beginAtZero:true}}}});
  },
  async dq() {
    const d = await api("/api/data-quality", {}, false), t = T();
    if (!d) return;
    const fa = lang === "fa";
    $("#dq").innerHTML = `<table><tr><th>${t.severity}</th><th>${t.table}</th><th class=n>${t.rows}</th><th>${t.issue}</th><th>${t.decision}</th></tr>` +
      d.issues.map(x => `<tr><td><span class="tag ${x.severity}">${x.severity}</span></td><td>${x.table_name}</td><td class=n>${x.n_rows}</td><td style="white-space:normal">${fa ? x.description_fa : x.description_en}</td><td style="white-space:normal">${fa ? x.decision_fa : x.decision_en}</td></tr>`).join("") + "</table>";
  }
};

async function refresh() {
  banner("");
  const l = loaders[state.tab]; if (l) await l();
}

// ------------------------------------------------------------------ static UI
function applyLang() {
  document.documentElement.lang = lang; document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
  $("#lang").textContent = lang === "fa" ? "EN" : "FA";
  document.querySelectorAll("[data-i18n]").forEach(e => { const v = T()[e.dataset.i18n]; if (v) e.textContent = v; });
  Chart.defaults.font.family = "Vazirmatn, system-ui, sans-serif";
  buildFilters(); buildSelects();
}
function opt(v, label, sel) { return `<option value="${v}" ${sel ? "selected" : ""}>${label}</option>`; }
function buildSelects() {
  const m = state.meta, t = T();
  const one = (id, vals) => { $("#f-" + id).innerHTML = opt("", t.all) + vals.map(v => opt(v, v, state.f[id] === v)).join(""); };
  one("employment_type", m.employment_types); one("work_location", m.work_locations); one("salary_grade", m.salary_grades);
  const months = (id) => { $("#f-" + id).innerHTML = opt("", t.all) + m.months.map(v => opt(v, monthLabel(v), state.f[id] === v)).join(""); };
  months("month_from"); months("month_to");
  $("#by").innerHTML = m.breakdown_fields.map(b => opt(b, t.bd[b] || b, b === ($("#by").dataset.v || "department"))).join("");
  $("#driver").innerHTML = Object.keys(t.drv).map(k => opt(k, t.drv[k], k === ($("#driver").dataset.v || "engagement"))).join("");
  buildManagers();
}
function buildManagers() {
  const m = state.meta, sel = state.f.department;
  const list = m.managers.filter(x => !sel.size || sel.has(x.department));
  $("#f-manager_id").innerHTML = list.map(x => opt(x.manager_id, x.manager_id, state.f.manager_id.has(x.manager_id))).join("");
}
function buildFilters() {
  const box = $("#f-department");
  box.innerHTML = state.meta.departments.map(d => `<span class="chip ${state.f.department.has(d) ? "on" : ""}" data-v="${d}">${tr("dept", d)}</span>`).join("");
  box.querySelectorAll(".chip").forEach(c => c.onclick = () => {
    const v = c.dataset.v; state.f.department.has(v) ? state.f.department.delete(v) : state.f.department.add(v);
    state.f.manager_id = new Set([...state.f.manager_id].filter(id => { const mm = state.meta.managers.find(x => x.manager_id === id); return !state.f.department.size || state.f.department.has(mm.department); }));
    c.classList.toggle("on"); buildManagers(); refresh();
  });
}
function wire() {
  document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => {
    document.querySelectorAll("#tabs button, .tab").forEach(e => e.classList.remove("active"));
    b.classList.add("active"); $("#tab-" + b.dataset.tab).classList.add("active"); state.tab = b.dataset.tab; refresh();
  });
  ["employment_type", "work_location", "salary_grade", "month_from", "month_to"].forEach(id => $("#f-" + id).onchange = e => { state.f[id] = e.target.value; refresh(); });
  $("#f-manager_id").onchange = e => { state.f.manager_id = new Set([...e.target.selectedOptions].map(o => o.value)); refresh(); };
  $("#by").onchange = e => { e.target.dataset.v = e.target.value; refresh(); };
  $("#driver").onchange = e => { e.target.dataset.v = e.target.value; refresh(); };
  $("#reset").onclick = () => { state.f = {department:new Set(), manager_id:new Set(), employment_type:"", work_location:"", salary_grade:"", month_from:"", month_to:""}; buildFilters(); buildSelects(); refresh(); };
  $("#lang").onclick = () => { lang = lang === "fa" ? "en" : "fa"; localStorage.setItem("lang", lang); applyLang(); refresh(); };
}
(async function init() {
  const meta = await api("/api/meta", {}, false);
  if (!meta) return;
  state.meta = meta; wire(); applyLang(); refresh();
})();
})();
