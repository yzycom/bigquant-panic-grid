"""
三频恐慌网格选股系统 - 抄底窗口筛选（固定价值池版）
===================================================
股票池来源: 价值池快照_20260508.md（截面日期 2026-05-08，TOP 200）
筛选逻辑（已固化在快照中，不再动态重算）:
    E/P(30%) + B/P(25%) + CFO/MV(25%) + 盈利收益率(20%)
硬约束: PE>0, PB>0, 流通市值>10亿, CFO>0, 非ST

本脚本职责:
    在固定价值池上跑三频恐慌网格抄底信号，统计抄底窗口出现频率。
    不负责重新构建价值池。如需更新池子，运行 export_value_pool.py。

注意:
    价值池是 2026-05-08 的固定截面，回看历史会带有幸存者/前视偏差。
    本脚本适合"在当前价值池中验证历史抄底窗口密度"，
    严谨历史回测请使用 step1_价值100选股频率验证.py（动态月末调仓版）。
"""
from bigmodule import M, I
import pandas as pd
import numpy as np
import dai

# ============================================================
# 参数
# ============================================================
ANALYSIS_START = "2022-07-01"
DATA_START = "2021-01-01"
END_DATE = "2026-05-08"

# 通达信公式参数
N1, N2, BW = 26, 10, 33
K = 4.5
HHV_N, VOL_REF, MID_REF = 120, 20, 5
DD_YELLOW, DD_PURPLE, DD_RED = 15, 25, 35

# 排雷阈值
MIN_AMOUNT_20_AVG = 50000000     # 20日日均成交额下限：5000万
MIN_CFFOA_TO_PROFIT = 0.3        # CFO / 净利润 最低现金含量

# ============================================================
# 价值池（来自 价值池快照_20260508.md，截面 2026-05-08，200 只）
# ============================================================
VALUE_POOL = [
    "000001.SZ", "000027.SZ", "000100.SZ", "000404.SZ", "000411.SZ",
    "000543.SZ", "000550.SZ", "000589.SZ", "000598.SZ", "000600.SZ",
    "000651.SZ", "000686.SZ", "000690.SZ", "000708.SZ", "000719.SZ",
    "000726.SZ", "000728.SZ", "000778.SZ", "000783.SZ", "000791.SZ",
    "000828.SZ", "000883.SZ", "000885.SZ", "000900.SZ", "000921.SZ",
    "000932.SZ", "000987.SZ", "000999.SZ", "001227.SZ", "001286.SZ",
    "001872.SZ", "001965.SZ", "002004.SZ", "002034.SZ", "002039.SZ",
    "002061.SZ", "002078.SZ", "002091.SZ", "002128.SZ", "002142.SZ",
    "002154.SZ", "002483.SZ", "002608.SZ", "002616.SZ", "002668.SZ",
    "002697.SZ", "002736.SZ", "002758.SZ", "002818.SZ", "002839.SZ",
    "002926.SZ", "002936.SZ", "002939.SZ", "002948.SZ", "002966.SZ",
    "301109.SZ", "600000.SH", "600004.SH", "600008.SH", "600011.SH",
    "600018.SH", "600019.SH", "600020.SH", "600023.SH", "600027.SH",
    "600028.SH", "600030.SH", "600033.SH", "600035.SH", "600036.SH",
    "600039.SH", "600050.SH", "600057.SH", "600060.SH", "600061.SH",
    "600064.SH", "600098.SH", "600104.SH", "600109.SH", "600170.SH",
    "600269.SH", "600282.SH", "600323.SH", "600368.SH", "600377.SH",
    "600380.SH", "600428.SH", "600461.SH", "600483.SH", "600502.SH",
    "600526.SH", "600528.SH", "600548.SH", "600551.SH", "600575.SH",
    "600578.SH", "600585.SH", "600642.SH", "600690.SH", "600694.SH",
    "600717.SH", "600729.SH", "600741.SH", "600742.SH", "600780.SH",
    "600795.SH", "600801.SH", "600803.SH", "600820.SH", "600827.SH",
    "600853.SH", "600861.SH", "600863.SH", "600874.SH", "600886.SH",
    "600908.SH", "600909.SH", "600919.SH", "600926.SH", "600938.SH",
    "600941.SH", "600958.SH", "600970.SH", "600987.SH", "600998.SH",
    "600999.SH", "601009.SH", "601033.SH", "601066.SH", "601077.SH",
    "601083.SH", "601107.SH", "601117.SH", "601139.SH", "601156.SH",
    "601163.SH", "601166.SH", "601169.SH", "601211.SH", "601229.SH",
    "601288.SH", "601298.SH", "601318.SH", "601319.SH", "601326.SH",
    "601328.SH", "601333.SH", "601336.SH", "601377.SH", "601390.SH",
    "601398.SH", "601518.SH", "601528.SH", "601555.SH", "601577.SH",
    "601598.SH", "601600.SH", "601601.SH", "601607.SH", "601628.SH",
    "601658.SH", "601665.SH", "601668.SH", "601669.SH", "601686.SH",
    "601688.SH", "601717.SH", "601728.SH", "601766.SH", "601788.SH",
    "601800.SH", "601808.SH", "601811.SH", "601818.SH", "601827.SH",
    "601838.SH", "601857.SH", "601860.SH", "601877.SH", "601881.SH",
    "601898.SH", "601900.SH", "601901.SH", "601916.SH", "601918.SH",
    "601919.SH", "601939.SH", "601963.SH", "601988.SH", "601991.SH",
    "601995.SH", "601998.SH", "603049.SH", "603071.SH", "603357.SH",
    "603368.SH", "603518.SH", "603689.SH", "603995.SH", "688330.SH",
]

# 去重 + 排序
VALUE_POOL = sorted(set(VALUE_POOL))
print("=" * 60)
print(f"价值池来源: 价值池快照_20260508.md  截面: 2026-05-08")
print(f"价值池数量: {len(VALUE_POOL)} 只")
if len(VALUE_POOL) != 200:
    print(f"⚠️ 警告: 期望 200 只, 实际 {len(VALUE_POOL)} 只")
print("=" * 60)

# ============================================================
# Step 1: 拉取价格数据（仅价值池股票）
# ============================================================
ins_str = "', '".join(VALUE_POOL)
price_sql = f"""
SELECT date, instrument,
       close, high, low, amount, adjust_factor
FROM cn_stock_bar1d
WHERE instrument IN ('{ins_str}')
  AND date >= '{DATA_START}' AND date <= '{END_DATE}'
ORDER BY instrument, date
"""
print("\n拉取价值池价格数据...")
df = dai.query(price_sql, filters={"date": [DATA_START, END_DATE]}).df()
print(f"  价格数据: {df['instrument'].nunique()} 只, {len(df)} 行")

df = df.sort_values(["instrument", "date"]).reset_index(drop=True)
df = df.dropna(subset=["close", "high", "low"])
if df["adjust_factor"].notna().any():
    df = df[df["adjust_factor"] > 0].copy()
    # cn_stock_bar1d 默认是后复权价，除以 adjust_factor 还原为不复权价
    for col in ["close", "high", "low"]:
        df[col] = df[col] / df["adjust_factor"]

# ============================================================
# Step 2: 拉取基本面 / 风险过滤字段
# ============================================================
print("拉取基本面与风险过滤字段...")
HAS_FUNDAMENTAL = False
try:
    fund_sql = f"""
    SELECT date, instrument, st_status, is_risk_warning,
           avg_amount_20,
           net_profit_to_parent_shareholders_ttm AS net_profit_ttm,
           net_cffoa_ttm, price_limit_status
    FROM cn_stock_factors
    WHERE instrument IN ('{ins_str}')
      AND date >= '{DATA_START}' AND date <= '{END_DATE}'
    """
    fund_df = dai.query(fund_sql, filters={"date": [DATA_START, END_DATE]}).df()
    df = df.merge(fund_df, on=["date", "instrument"], how="left")
    HAS_FUNDAMENTAL = True
    print(f"  基本面: {len(fund_df)} 行")
except Exception as e:
    print(f"  基本面拉取失败: {e}")
    df["st_status"] = 0
    df["is_risk_warning"] = 0

# ============================================================
# Step 3: 计算技术指标
# ============================================================
print("\n计算技术指标...")

def compute_indicators(g):
    """单只股票计算 EMA 趋势、EWMA 通道、恐慌仪表"""
    g = g.copy()
    c, h, l = g["close"], g["high"], g["low"]
    if len(g) < 200:
        return pd.DataFrame()

    # EMA 四线趋势
    for p in [50, 100, 150, 200]:
        g[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()
    bull = (g["ema50"] > g["ema100"]) & (g["ema100"] > g["ema150"]) & (g["ema150"] > g["ema200"])
    bear = (g["ema50"] < g["ema100"]) & (g["ema100"] < g["ema150"]) & (g["ema150"] < g["ema200"])
    g["trend"] = "Range"
    g.loc[bull, "trend"] = "Bull"
    g.loc[bear, "trend"] = "Bear"

    # EWMA 通道
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    band = tr.ewm(span=BW, adjust=False).mean()
    mid = c.ewm(span=N1, adjust=False).mean().ewm(span=N2, adjust=False).mean()
    g["ewma_buy"] = l <= (mid - K * band)

    # 恐慌仪表
    hh = h.rolling(window=HHV_N, min_periods=1).max()
    dd = (hh - c) / hh * 100
    vol_expand = band > band.shift(VOL_REF) * 1.5
    mid_down = mid < mid.shift(MID_REF)
    crash = vol_expand & mid_down

    g["panic"] = "green"
    g.loc[(dd >= DD_YELLOW) & ((dd < DD_PURPLE) | ~crash), "panic"] = "yellow"
    g.loc[(dd >= DD_PURPLE) & (dd < DD_RED) & crash, "panic"] = "purple"
    g.loc[(dd >= DD_RED) & crash, "panic"] = "red"
    g["drawdown_pct"] = dd
    g["was_bull_2d"] = bull.rolling(window=2, min_periods=1).sum() > 0

    # CFO 现金含量
    if HAS_FUNDAMENTAL and "net_profit_ttm" in g.columns:
        g["cffoa_to_profit"] = g["net_cffoa_ttm"] / g["net_profit_ttm"].replace(0, np.nan)
    return g

result = df.groupby("instrument", group_keys=False).apply(compute_indicators).reset_index(drop=True)
print(f"  指标计算完成: {len(result)} 行, {result['instrument'].nunique()} 只")

# ============================================================
# Step 4: 抄底窗口筛选条件
# ============================================================
r = result[result["date"] >= ANALYSIS_START].copy()
r["date"] = pd.to_datetime(r["date"])

# 买入池：价值池 + 排雷
buy_pool = r["instrument"].isin(VALUE_POOL)
buy_pool &= r["st_status"].fillna(0).eq(0)
buy_pool &= r["is_risk_warning"].fillna(0).eq(0)

if HAS_FUNDAMENTAL:
    buy_pool &= r["net_profit_ttm"].fillna(-np.inf) > 0
    buy_pool &= r["net_cffoa_ttm"].fillna(-np.inf) > 0
    if "cffoa_to_profit" in r.columns:
        buy_pool &= r["cffoa_to_profit"].fillna(-np.inf) >= MIN_CFFOA_TO_PROFIT
    if "avg_amount_20" in r.columns:
        buy_pool &= r["avg_amount_20"].fillna(0) >= MIN_AMOUNT_20_AVG
    if "price_limit_status" in r.columns:
        # price_limit_status: 1=跌停, 2=非涨跌停, 3=涨停
        buy_pool &= r["price_limit_status"].fillna(2).ne(1)

print(f"\n买入池行数: {int(buy_pool.sum())}")

# 抄底窗口三频条件
c_bull  = buy_pool & (r["trend"] == "Bull")  & r["panic"].isin(["yellow", "purple", "red"]) & r["ewma_buy"]
c_range = buy_pool & (r["trend"] == "Range") & r["panic"].isin(["purple", "red"])           & r["ewma_buy"]
c_bear  = buy_pool & (r["trend"] == "Bear")  & r["panic"].isin(["purple", "red"])           & r["ewma_buy"]
# Bull → Range 过渡：前 2 日内曾为 Bull，允许黄色
c_trans = buy_pool & (r["trend"] == "Range") & (r["panic"] == "yellow") & r["ewma_buy"] & r["was_bull_2d"]

r["selected"] = c_bull | c_range | c_bear | c_trans
r["stype"] = ""
r.loc[c_bull,  "stype"] = "Bull"
r.loc[c_range, "stype"] = "Range"
r.loc[c_bear,  "stype"] = "Bear"
r.loc[c_trans, "stype"] = "Range→Bull"

sel = r[r["selected"]]
print(f"抄底窗口命中: {len(sel)} 行")

# ============================================================
# Step 5: 去重（连续命中合并为一次抄底信号）
# ============================================================
sel_out = sel[["date", "instrument", "trend", "panic", "drawdown_pct", "stype"]].copy()
sel_out = sel_out.sort_values(["date", "instrument"]).reset_index(drop=True)
sel_out.to_csv("抄底窗口_daily_hits.csv", index=False)

all_dates = r["date"].sort_values().unique()
all_dl = list(all_dates)

signals = []
for ins, grp in sel_out.groupby("instrument"):
    dates = sorted(grp["date"].unique())
    if not dates:
        continue
    seg_start = prev = dates[0]
    for i in range(1, len(dates)):
        curr = dates[i]
        pi = all_dl.index(prev) if prev in all_dl else -1
        ci = all_dl.index(curr) if curr in all_dl else -1
        if ci != pi + 1:
            fr = grp[grp["date"] == seg_start].iloc[0]
            signals.append({
                "instrument": ins, "first_date": seg_start, "last_date": prev,
                "days": len([d for d in dates if seg_start <= d <= prev]),
                "trend": fr["trend"], "panic": fr["panic"],
                "drawdown_pct": round(fr["drawdown_pct"], 1),
            })
            seg_start = curr
        prev = curr
    fr = grp[grp["date"] == seg_start].iloc[0]
    signals.append({
        "instrument": ins, "first_date": seg_start, "last_date": prev,
        "days": len([d for d in dates if seg_start <= d <= prev]),
        "trend": fr["trend"], "panic": fr["panic"],
        "drawdown_pct": round(fr["drawdown_pct"], 1),
    })

signals_df = pd.DataFrame(signals)
if len(signals_df) > 0:
    signals_df = signals_df.sort_values("first_date").reset_index(drop=True)
signals_df.to_csv("抄底窗口_buy_signals.csv", index=False)

# ============================================================
# Step 6: 频率统计
# ============================================================
if len(sel) > 0:
    daily = sel.groupby("date").agg(
        total=("instrument", "count"),
        bull=("stype",  lambda x: (x == "Bull").sum()),
        rng=("stype",   lambda x: (x == "Range").sum()),
        bear=("stype",  lambda x: (x == "Bear").sum()),
        trans=("stype", lambda x: (x == "Range→Bull").sum()),
    ).reset_index()
    daily = daily.set_index("date").reindex(all_dates, fill_value=0).reset_index()
else:
    daily = pd.DataFrame({"date": all_dates, "total": 0, "bull": 0, "rng": 0, "bear": 0, "trans": 0})

if len(signals_df) > 0:
    dn = signals_df.groupby("first_date").size().reset_index(name="new_signals")
    dn.columns = ["date", "new_signals"]
    daily = daily.merge(dn, on="date", how="left")
daily["new_signals"] = daily.get("new_signals", 0).fillna(0).astype(int)

# 导出汇总指标
n_days = len(all_dates)
avg_raw = daily["total"].mean() if n_days > 0 else 0
avg_new = daily["new_signals"].mean() if n_days > 0 else 0
summary_rows = [
    ("价值池来源", "价值池快照_20260508.md (截面 2026-05-08)"),
    ("价值池数量", len(VALUE_POOL)),
    ("分析起", str(all_dates[0])[:10] if n_days > 0 else ""),
    ("分析止", str(all_dates[-1])[:10] if n_days > 0 else ""),
    ("交易日数", n_days),
    ("原始命中行数", int(daily["total"].sum())),
    ("去重信号数", len(signals_df)),
    ("每日原始命中均值", round(avg_raw, 2)),
    ("每日原始命中中位数", float(daily["total"].median()) if n_days > 0 else 0),
    ("每日原始命中P75", float(daily["total"].quantile(.75)) if n_days > 0 else 0),
    ("每日原始命中P95", float(daily["total"].quantile(.95)) if n_days > 0 else 0),
    ("每日原始命中最大", int(daily["total"].max()) if n_days > 0 else 0),
    ("每日新信号均值", round(avg_new, 2)),
    ("参数K", K),
    ("阈值yellow", DD_YELLOW),
    ("阈值purple", DD_PURPLE),
    ("阈值red", DD_RED),
]
summary_df = pd.DataFrame(summary_rows, columns=["metric", "value"])
summary_df.to_csv("抄底窗口_frequency_summary.csv", index=False)

# ============================================================
# Step 7: 控制台报告
# ============================================================
print(f"\n{'=' * 60}")
print(f"抄底窗口频率验证报告（固定价值池版）")
print(f"{'=' * 60}")
print(f"价值池: 固定 {len(VALUE_POOL)} 只（来源 价值池快照_20260508.md）")
print(f"区间: {str(all_dates[0])[:10]} ~ {str(all_dates[-1])[:10]}, {n_days} 个交易日")
print(f"参数: K={K}, 阈值={DD_YELLOW}/{DD_PURPLE}/{DD_RED}")
print(f"\n--- 原始命中（含连续重复）---")
print(f"每日: 均值={avg_raw:.1f}, 中位={daily['total'].median():.0f}, "
      f"P75={daily['total'].quantile(.75):.0f}, P95={daily['total'].quantile(.95):.0f}, "
      f"最大={daily['total'].max()}")
print(f"\n--- 去重独立抄底信号 ---")
print(f"总信号数: {len(signals_df)}, "
      f"平均持续 {signals_df['days'].mean():.1f} 天" if len(signals_df) > 0 else "总信号数: 0")
print(f"每日新信号: 均值={avg_new:.2f}")

if len(signals_df) > 0:
    print(f"\n趋势:", end="")
    for t in ["Bull", "Range", "Bear"]:
        cnt = (signals_df["trend"] == t).sum()
        print(f" {t}={cnt}({cnt/len(signals_df)*100:.0f}%)", end="")
    print(f"\n颜色:", end="")
    for cc in ["yellow", "purple", "red"]:
        cnt = (signals_df["panic"] == cc).sum()
        print(f" {cc}={cnt}({cnt/len(signals_df)*100:.0f}%)", end="")
    dd_col = signals_df["drawdown_pct"]
    print(f"\n回撤: 均{dd_col.mean():.1f}% 中位{dd_col.median():.1f}% 最大{dd_col.max():.1f}%")

# 频率简评
print(f"\n{'=' * 60}")
if avg_new <= 2:
    print(f"⚠️ 抄底窗口偏少（{avg_new:.2f} 新信号/日），条件可能过严")
elif avg_new <= 10:
    print(f"✅ 抄底窗口频率合理（{avg_new:.2f} 新信号/日）")
elif avg_new <= 25:
    print(f"⚠️ 抄底窗口偏高（{avg_new:.2f} 新信号/日），需收紧")
else:
    print(f"🚨 抄底窗口过高（{avg_new:.2f} 新信号/日），需大幅收紧")

# 2026 年以来命中明细
print(f"\n--- 2026 年以来抄底窗口明细 ---")
dates_2026 = [d for d in sorted(all_dates) if str(d)[:4] >= "2026"]
shown = 0
for d in dates_2026:
    d_str = str(d)[:10]
    day_sel = sel_out[sel_out["date"] == d]
    n = len(day_sel)
    if n == 0:
        continue
    day_row = daily[daily["date"] == d]
    day_new = int(day_row["new_signals"].iloc[0]) if len(day_row) > 0 else 0
    day_b  = int(day_row["bull"].iloc[0]) if len(day_row) > 0 else 0
    day_r  = int(day_row["rng"].iloc[0])  if len(day_row) > 0 else 0
    day_be = int(day_row["bear"].iloc[0]) if len(day_row) > 0 else 0
    print(f"{d_str}  命中:{n:3d}  新:{day_new:2d}  B:{day_b:2d} R:{day_r:2d} Be:{day_be:2d}")
    for _, hit in day_sel.iterrows():
        print(f"    {hit['instrument']}  {hit['trend']:5s}  {hit['panic']:6s}  回撤:{hit['drawdown_pct']:.1f}%")
    shown += 1
if shown == 0:
    print("  （区间内无 2026 年命中）")

# 按标的统计
if len(signals_df) > 0:
    print(f"\n--- 按标的（前15）---")
    top = signals_df.groupby("instrument").agg(
        次数=("first_date", "count"), 均回撤=("drawdown_pct", "mean")
    ).reset_index().sort_values("次数", ascending=False).head(15)
    top["均回撤"] = top["均回撤"].round(1)
    print(top.to_string(index=False))

print(f"\n已导出:")
print(f"  抄底窗口_daily_hits.csv         （每日命中明细）")
print(f"  抄底窗口_buy_signals.csv        （去重买入信号）")
print(f"  抄底窗口_frequency_summary.csv  （频率统计汇总）")
