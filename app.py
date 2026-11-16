from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# ── Configuration ──────────────────────────────────────────────
st.set_page_config(page_title="Global B2B Sales Intensity", layout="wide")

FICHIER = Path(__file__).parent / "Copy of Business case - Global B2B sales intensity (OnePulse extract).xlsx"
ANNEES = [2025, 2026]
COULEURS = alt.Scale(domain=["2025", "2026"], range=["#8A8A8A", "#0078A8"])
NOMS_MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]


# ── Data loading (cached) ──────────────────────────────────────
@st.cache_data(show_spinner="Loading data…", max_entries=1)
def charger_donnees(chemin, modification):
    df = pd.read_excel(chemin, sheet_name="Deals")
    df["Signature date"] = pd.to_datetime(df["Signature date"], errors="coerce")

    # Like-for-like scope: Supply, January–September 2025 and 2026
    masque = (
        df["Signature date"].dt.year.isin(ANNEES)
        & df["Signature date"].dt.month.le(9)
        & df["Flow"].eq("Supply")
    )
    base = df.loc[masque].copy()
    base["Annee"] = base["Signature date"].dt.year
    base["Mois"] = base["Signature date"].dt.month
    return base


if not FICHIER.exists():
    st.error(f"File not found: {FICHIER.name}. Please check its name and location.")
    st.stop()

base = charger_donnees(str(FICHIER), FICHIER.stat().st_mtime)


# ── Calculation functions ──────────────────────────────────────
def agreger(donnees, niveaux):
    """Deals, volume, margin and margin per MWh by levels + year."""
    t = donnees.groupby(niveaux + ["Annee"]).agg(
        Deals=("Deal ID", "nunique"),
        Volume_MWh=("Physical volume (MWh)", "sum"),
        MARGIN_EUR=("Margin at signature (EUR)", "sum"),
    )
    t["MARGIN_par_MWh"] = t["MARGIN_EUR"] / t["Volume_MWh"].where(t["Volume_MWh"].gt(0))
    return t


def comparer(serie, facteur=1, remplir=False):
    """Transforms a series (…, Annee) into a 2025 / 2026 / Change / Change (%) table."""
    t = serie.unstack("Annee").reindex(columns=ANNEES)
    if remplir:
        t = t.fillna(0)
    t = t / facteur
    t.columns = ["2025", "2026"]
    t["Change"] = t["2026"] - t["2025"]
    t["Change (%)"] = t["Change"] / t["2025"].where(t["2025"].gt(0)) * 100
    return t


def afficher(tableau, decimales=0):
    fmt = {
        "2025": f"{{:,.{decimales}f}}",
        "2026": f"{{:,.{decimales}f}}",
        "Change": f"{{:+,.{decimales}f}}",
        "Change (%)": "{:+.1f}",
    }
    fmt = {k: v for k, v in fmt.items() if k in tableau.columns}
    st.dataframe(tableau.style.format(fmt, na_rep="—"), use_container_width=True)


def evolution(avant, apres):
    if avant <= 0:
        return None
    return f"{(apres / avant - 1) * 100:+.1f}% vs 2025"


# ── Chart functions ────────────────────────────────────────────
def graphique_courbes(tableau, titre, axe_y):
    donnees = (
        tableau.rename_axis("Month").reset_index()
        .melt(id_vars="Month", var_name="Year", value_name="Value")
    )
    donnees["Month"] = donnees["Month"].map(lambda m: NOMS_MOIS[m - 1])

    graphique = (
        alt.Chart(donnees, title=titre)
        .mark_line(point=True)
        .encode(
            x=alt.X("Month:N", sort=NOMS_MOIS, title="Signature month",
                    axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Value:Q", title=axe_y),
            color=alt.Color("Year:N", scale=COULEURS, title="Year"),
            tooltip=["Year", "Month", alt.Tooltip("Value:Q", format=",.2f")],
        )
    )
    st.altair_chart(graphique, use_container_width=True)


def graphique_barres(tableau, titre, axe_y, axe_x="Business unit"):
    donnees = (
        tableau[["2025", "2026"]].rename_axis("Category").reset_index()
        .melt(id_vars="Category", var_name="Year", value_name="Value")
    )

    graphique = (
        alt.Chart(donnees, title=titre)
        .mark_bar()
        .encode(
            x=alt.X("Category:N", title=axe_x, axis=alt.Axis(labelAngle=0)),
            xOffset="Year:N",
            y=alt.Y("Value:Q", title=axe_y),
            color=alt.Color("Year:N", scale=COULEURS, title="Year"),
            tooltip=["Category", "Year", alt.Tooltip("Value:Q", format=",.2f")],
        )
    )
    st.altair_chart(graphique, use_container_width=True)


# ── Header and sidebar filter ──────────────────────────────────
st.title("Global B2B Sales Intensity")
st.caption("Contracts signed from January to September: 2025 vs 2026 comparison (Supply flow)")
st.warning("Case Study: Graduate Programme Sales & Business Performance ")

segment = st.sidebar.selectbox("Segment", ["SME & Mid-market", "Large Accounts"])
st.sidebar.caption(
    "This filter applies to tabs 1 to 3. "
    "Large Accounts (LA) is analysed separately from country BUs."
)

selection = base.loc[base["Segment"].eq(segment)].copy()
bus = sorted(selection["Business unit"].unique())

onglets = st.tabs([
    "1. Global Overview",
    "2. Quarterly & Monthly Momentum",
    "3. Drivers & Value",
    "4. Sales Teams",
    "5. Executive Summary & Actions",
])


# ═══════════════ 1. GLOBAL OVERVIEW ═══════════════════════════
with onglets[0]:
    st.header(f"Global Overview — {segment}")
    st.caption("All offer types and all event types included (including automatic tacit renewals).")

    kpi = agreger(selection, []).reindex(ANNEES, fill_value=0)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Deals signed — 2026",
        f"{int(kpi.loc[2026, 'Deals']):,}",
        delta=evolution(kpi.loc[2025, "Deals"], kpi.loc[2026, "Deals"]),
        delta_color="off",
    )
    c2.metric(
        "Expected margin at signature — 2026",
        f"€{kpi.loc[2026, 'MARGIN_EUR'] / 1e6:.2f}M",
        delta=evolution(kpi.loc[2025, "MARGIN_EUR"], kpi.loc[2026, "MARGIN_EUR"]),
        delta_color="off",
    )
    c3.metric(
        "Physical volume contracted — 2026",
        f"{kpi.loc[2026, 'Volume_MWh'] / 1e6:.2f} TWh",
        delta=evolution(kpi.loc[2025, "Volume_MWh"], kpi.loc[2026, "Volume_MWh"]),
        delta_color="off",
    )
    st.info(
        "Expected margin and physical volume cover the full contract duration, "
        "not only the year of signature."
    )

    st.subheader("Comparison by Business Unit")
    par_bu = agreger(selection, ["Business unit"])
    t_deals, t_MARGIN, t_volume = st.tabs(["Number of deals", "Expected margin (€M)", "Physical volume (TWh)"])

    with t_deals:
        afficher(comparer(par_bu["Deals"], remplir=True).sort_values("Change", ascending=False))
    with t_MARGIN:
        afficher(comparer(par_bu["MARGIN_EUR"], 1e6, True).sort_values("Change", ascending=False), 2)
    with t_volume:
        afficher(comparer(par_bu["Volume_MWh"], 1e6, True).sort_values("Change", ascending=False), 2)

    st.subheader("Breakdown by Event Type")
    bu_evt = st.selectbox("Select Business Unit", bus, key="bu_evt")
    evt = agreger(selection.loc[selection["Business unit"].eq(bu_evt)], ["Event type"])
    deals_evt = comparer(evt["Deals"], remplir=True)
    MARGIN_evt = comparer(evt["MARGIN_EUR"], 1e6, True)

    tableau_evt = pd.DataFrame({
        "Deals 2025": deals_evt["2025"],
        "Deals 2026": deals_evt["2026"],
        "Deal change": deals_evt["Change"],
        "Margin 2025 (€M)": MARGIN_evt["2025"],
        "Margin 2026 (€M)": MARGIN_evt["2026"],
        "Margin change (€M)": MARGIN_evt["Change"],
    })
    st.dataframe(tableau_evt.style.format({
        "Deals 2025": "{:,.0f}", "Deals 2026": "{:,.0f}", "Deal change": "{:+,.0f}",
        "Margin 2025 (€M)": "{:,.2f}", "Margin 2026 (€M)": "{:,.2f}",
        "Margin change (€M)": "{:+,.2f}",
    }), use_container_width=True)
    st.caption("Note: 'Renewal' does not specify whether the renewal is tacit or non-tacit.")


# ═══════════════ 2. QUARTERLY & MONTHLY MOMENTUM ══════════════
with onglets[1]:
    st.header(f"Quarterly & Monthly Momentum — {segment}")
    st.caption(
        "Each period in 2026 is compared with the same period in 2025. "
        "Strong cumulative figures can hide a recent slowdown."
    )

    # ── Quarterly view ──
    q = selection.assign(
        Quarter="Q" + ((selection["Mois"] - 1) // 3 + 1).astype(str)
    )
    t = (
        q.groupby(["Business unit", "Quarter", "Annee"])["Margin at signature (EUR)"]
        .sum()
        .unstack("Annee")
    )
    trim = ((t[2026] / t[2025] - 1) * 100).drop("MX", level="Business unit", errors="ignore")
    trim = trim.rename("Change").reset_index().rename(columns={"Business unit": "BU"})

    chart = (
        alt.Chart(trim, title="Expected margin by quarter — 2026 vs 2025 (%)")
        .mark_bar()
        .encode(
            x=alt.X("BU:N", sort=["FR", "UK", "US", "NL", "PL", "BE", "RO"],
                    title="Business unit", axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("Quarter:N", sort=["Q1", "Q2", "Q3"]),
            y=alt.Y("Change:Q", title="Change vs 2025 (%)"),
            color=alt.Color("Quarter:N", title="Quarter",
                            scale=alt.Scale(domain=["Q1", "Q2", "Q3"],
                                            range=["#D5D8DC", "#95A5A6", "#0078A8"])),
            tooltip=["BU", "Quarter", alt.Tooltip("Change:Q", format="+.0f")],
        )
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption("Mexico excluded from the chart (small base: 33 deals in 2025).")

    st.subheader("Monthly Curves by Business Unit")
    bu_mois = st.selectbox("Select Business Unit", bus, key="bu_mois")
    mensuel = agreger(selection.loc[selection["Business unit"].eq(bu_mois)], ["Mois"])

    def courbe(indicateur, facteur=1):
        t = (
            mensuel[indicateur].unstack("Annee")
            .reindex(index=range(1, 10), columns=ANNEES)
            .fillna(0) / facteur
        )
        t.columns = ["2025", "2026"]
        return t

    c1, c2, c3 = st.columns(3)
    with c1:
        graphique_courbes(courbe("Deals"), f"{bu_mois} — Number of deals signed", "Number of deals")
    with c2:
        graphique_courbes(courbe("Volume_MWh", 1e6), f"{bu_mois} — Physical volume contracted", "Volume (TWh)")
    with c3:
        graphique_courbes(courbe("MARGIN_EUR", 1e6), f"{bu_mois} — Expected margin at signature", "Margin (€M)")


# ═══════════════ 3. DRIVERS & VALUE ═══════════════════════════
with onglets[2]:
    st.header(f"Drivers & Value — {segment}")

    # 1. Sales Channel
    st.subheader("1. Sales Channel Model: Direct vs. Indirect (Brokers)")
    canal_global = (
        selection.loc[selection["Annee"].eq(2026)]
        .groupby(["Business unit", "Sales channel"])["Deal ID"]
        .nunique()
        .reset_index(name="Deals")
    )

    chart_canal_global = (
        alt.Chart(canal_global, title="Share of deals by sales channel in 2026 (%)")
        .mark_bar()
        .encode(
            x=alt.X("Business unit:N", title="Business unit", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Deals:Q", stack="normalize", title="Share of deals (%)", axis=alt.Axis(format="%")),
            color=alt.Color(
                "Sales channel:N",
                title="Channel",
                scale=alt.Scale(domain=["Direct", "Indirect"], range=["#0078A8", "#8A8A8A"])
            ),
            tooltip=["Business unit", "Sales channel", "Deals"]
        )
    )
    st.altair_chart(chart_canal_global, use_container_width=True)

    # 2. Unit margin by Energy
    st.subheader("2. Unit Margin (€/MWh) — Overall & by Energy")
    st.caption("Unit margin = Total expected margin / Total physical volume (volume-weighted average).")

    mwh_global = comparer(agreger(selection, ["Business unit"])["MARGIN_par_MWh"])
    col_g, col_t = st.columns(2)
    with col_g:
        graphique_barres(mwh_global, f"Unit margin (All energies) — {segment}", "€/MWh")
    with col_t:
        afficher(mwh_global, 2)

    par_energie = agreger(selection, ["Energy", "Business unit"])
    energies = par_energie.index.get_level_values("Energy").unique()

    for colonne, energie in zip(st.columns(2), ["Power", "Gas"]):
        with colonne:
            if energie not in energies:
                st.info(f"No {energie} deals in this scope.")
                continue
            detail = comparer(par_energie.xs(energie, level="Energy")["MARGIN_par_MWh"])
            graphique_barres(detail, f"Margin per MWh — {energie} (€/MWh)", "€/MWh")
            afficher(detail, 2)

    st.info(
        "Compare each BU's evolution between 2025 and 2026 rather than absolute levels across countries "
        "(different market structures and modified margins)."
    )

    # 3. Weighted average vs Median
    st.subheader("3. Portfolio vs. Typical Deal: Weighted Average & Median (€/MWh)")
    st.caption(
        "Scope: Physical supply offers only, with positive volume. "
        "Weighted average is sensitive to very large deals; Median reflects the typical deal."
    )

    physique = selection.loc[
        selection["Offer type"].eq("Physical supply")
        & selection["Physical volume (MWh)"].gt(0)
    ].copy()
    physique["MARGIN_MWh_deal"] = (
        physique["Margin at signature (EUR)"] / physique["Physical volume (MWh)"]
    )

    stats = physique.groupby(["Energy", "Business unit", "Annee"]).agg(
        MARGIN=("Margin at signature (EUR)", "sum"),
        Volume=("Physical volume (MWh)", "sum"),
        Median=("MARGIN_MWh_deal", "median"),
    )
    stats["Weighted average"] = stats["MARGIN"] / stats["Volume"]

    energie_choisie = st.radio(
        "Select Energy",
        sorted(stats.index.get_level_values("Energy").unique()),
        horizontal=True,
        key="energie_mediane",
    )
    moyenne = comparer(stats.xs(energie_choisie, level="Energy")["Weighted average"])
    mediane = comparer(stats.xs(energie_choisie, level="Energy")["Median"])

    col_m, col_d = st.columns(2)
    with col_m:
        graphique_barres(moyenne, f"Weighted average — {energie_choisie} (€/MWh)", "€/MWh")
    with col_d:
        graphique_barres(mediane, f"Median deal — {energie_choisie} (€/MWh)", "€/MWh")

    synthese = pd.DataFrame({
        "Average 2025": moyenne["2025"], "Average 2026": moyenne["2026"],
        "Average change (%)": moyenne["Change (%)"],
        "Median 2025": mediane["2025"], "Median 2026": mediane["2026"],
        "Median change (%)": mediane["Change (%)"],
    })
    st.dataframe(synthese.style.format({
        "Average 2025": "{:.2f}", "Average 2026": "{:.2f}", "Average change (%)": "{:+.1f}",
        "Median 2025": "{:.2f}", "Median 2026": "{:.2f}", "Median change (%)": "{:+.1f}",
    }, na_rep="—"), use_container_width=True)
    st.info(
        "Average down & Median stable = driven by a few large low-margin contracts (e.g., UK). "
        "Both down = the typical deal is less profitable (e.g., US Power)."
    )


# ═══════════════ 4. SALES TEAMS ═══════════════════════════════
with onglets[3]:
    st.header("Sales Teams Productivity")
    st.caption("This tab covers all BUs independently of the segment filter.")

    st.subheader("Sales Rep ID Coverage (% of deals with a rep assigned)")
    couverture = (
        base.assign(Renseigne=base["Sales rep ID"].notna())
        .groupby(["Business unit", "Annee"])["Renseigne"].mean()
        .mul(100).unstack("Annee")
    )
    couverture.columns = ["2025 (%)", "2026 (%)"]
    st.dataframe(couverture.style.format("{:.1f}"), use_container_width=True)
    st.warning("Sales rep ID is missing (0%) in BE, UK, PL, RO, and LA: team productivity cannot be tracked there.")

    st.subheader("Productivity per Active Sales Rep — FR, NL, US")
    st.caption(
        "Excludes automatic tacit renewals. Active sales reps = reps with at least one signed deal "
        "(does not reflect total headcount)."
    )

    reps = base.loc[
        base["Sales rep ID"].notna()
        & base["Business unit"].isin(["FR", "NL", "US"])
        & base["Event type"].ne("Tacit renewal")
    ]
    par_rep = (
        reps.groupby(["Business unit", "Annee", "Sales rep ID"])
        .agg(Deals=("Deal ID", "nunique"), MARGIN_EUR=("Margin at signature (EUR)", "sum"))
        .reset_index()
    )
    productivite = (
        par_rep.groupby(["Business unit", "Annee"])
        .agg(
            Commerciaux_actifs=("Sales rep ID", "nunique"),
            Deals_moyen=("Deals", "mean"),
            Deals_median=("Deals", "median"),
            MARGIN_moyenne_kEUR=("MARGIN_EUR", lambda s: s.mean() / 1000),
        )
        .unstack("Annee")
    )
    noms = {
        "Commerciaux_actifs": "Active reps",
        "Deals_moyen": "Deals per rep (avg)",
        "Deals_median": "Deals per rep (median)",
        "MARGIN_moyenne_kEUR": "Margin per rep (k€)",
    }
    productivite.columns = [f"{noms[i]} {a}" for i, a in productivite.columns]
    st.dataframe(productivite.style.format("{:,.1f}"), use_container_width=True)

    deals_rep = comparer(
        par_rep.groupby(["Business unit", "Annee"])["Deals"].mean()
    )
    MARGIN_rep = comparer(
        par_rep.groupby(["Business unit", "Annee"])["MARGIN_EUR"].mean(),
        facteur=1000
    )

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        graphique_barres(deals_rep, "Average deals per active sales rep", "Deals per rep")
    with col_r2:
        graphique_barres(MARGIN_rep, "Average margin per active sales rep (k€)", "Margin (k€)")


# ═══════════════ 5. EXECUTIVE SUMMARY & ACTIONS ═══════════════
with onglets[4]:
    st.header("Executive Summary & Recommended Actions")

    # 1. What the data tells us
    st.subheader("1. What the data tells us (Jan–Sep 2026 vs. Jan–Sep 2025)")
    st.markdown("""
- **Opposite segment trends:** **Large Accounts** grows across all metrics (Deals +11%, Margin +24%, Volume +54%), though Q3 slowed down (−42%). **SME & Mid-market** declines in deals (−9.4%) and expected margin (−5.7%, to €500.2M).
- **Volume growth is misleading:** SME volume appears up +20%, but **without Mexico, volume is flat** (UK volume gains offset France's losses).
- **Momentum is slowing down in Q3:** Expected margin drops year-over-year in Q3 across our largest BUs (**FR −31%, UK −39%, US −23%, NL −38%**), already visible in July–August.
- **Two distinct sales models:** FR (85%), BE (76%) and RO (100%) rely on **direct sales**, whereas US (97%), NL (98%), UK (88%) and PL (72%) rely on **brokers**.
""")

    # 2. Three key insights
    st.subheader("2. The Three Most Important Insights (FR, UK, US = 72% of SME Margin)")
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1:
        st.markdown("""
**France: Direct acquisition drops, price holds**
- Margin **−20% (−€37.7M)**, including −€31.2M on acquisitions.
- **98%** of the margin loss comes from direct sales.
- Unit margins are up in Power (+4%) and Gas (+29%): **pricing is not the issue**.
- More active reps (171 → 192), but margin per rep is down **−32%**.
""")
    with col_i2:
        st.markdown("""
**UK: Volume doubles on low-margin deals**
- Deals −21%, volume **+122%**, margin only **+5%**.
- **88%** of extra volume comes from large direct deals at ~€1.3/MWh.
- Average €/MWh halves, but **median deal €/MWh is stable**: the typical deal is unchanged.
- Below 2025 margin **every month from May to September**.
""")
    with col_i3:
        st.markdown("""
**US (and NL): More deals, not more value**
- US deals **+35%** (+3,077 acquisitions), but margin **−8%** (−€7.5M on acquisitions).
- Median Power €/MWh drops **−46%** and broker deal size drops **−30%**.
- Deals per active rep jump **+54%** (US) and **+57%** (NL), while margin per rep barely moves (+5% to +7%).
""")

    st.divider()

    # 3. Limitations & 4. Actions
    col_l, col_a = st.columns(2)
    with col_l:
        st.subheader("3. Main Limitations & Missing Data")
        st.markdown("""
- **No pipeline / lost deals data:** We only see signed deals, so we cannot measure conversion rates or know why deals are lost.
- **Missing `Sales rep ID` in 5 of 9 BUs:** Impossible to track team productivity in the UK, BE, PL, RO, and LA (and ~25% of FR deals).
- **No sales targets or real headcount:** We can only compare 2026 to 2025, not to budget targets or actual team size / ramp-up time.
- **Broker commissions unknown:** We do not know if broker commissions are deducted from `Margin at signature`.
""")

    with col_a:
        st.subheader("4. Recommended Global Actions")
        st.markdown("""
1. **Push higher-margin energy (Power) & cross-sell:** Power generates a higher €/MWh than Gas across markets. Push Power acquisition and systematic dual-fuel (Power + Gas) offers.
2. **Defend unit margins on weaker segments:** Stop using price cuts to win volume on Gas and very large contracts; enforce a strict minimum €/MWh floor.
3. **Shift targets from deal count to deal value:** Align both direct sales reps (FR) and broker incentives (US, NL, UK) on total margin and €/MWh rather than contract quantity.
4. **Fix global tracking in OnePulse:** Make `Sales rep ID` mandatory across all 9 BUs and integrate open/lost opportunities to track conversion.
""")

    st.divider()

    # 5. Global Sales Initiative
    st.subheader("5. Global Sales Community Initiative: 'The Smart Deal League' (Quarterly)")
    st.info(
        "**Why quarterly?** B2B energy sales take weeks or months to prospect and negotiate. "
        "Measuring progress every quarter rewards sustainable deal quality rather than end-of-month price cutting.\n\n"
        "**3 Quarterly Spotlights (measured on relative QoQ progress against each BU's own baseline):**\n"
        "- **The Value Booster:** Highest improvement in median unit margin (€/MWh).\n"
        "- **The Power & Dual-Fuel Striker:** Strongest growth in Power and combined Power + Gas contracts.\n"
        "- **The Acquisition Mover:** Strongest progression in active new customer acquisitions."
    )

    # 6. Assumptions & KPI definitions
    st.subheader("6. Assumptions & KPI Definitions")
    st.markdown("""
| KPI / Assumption | Definition |
|---|---|
| **Like-for-like scope** | Signatures from Jan 1 to Sep 30, 2025 vs. Jan 1 to Sep 30, 2026. `Supply` flow only (`Injection` excluded). |
| **Deals signed** | Count of unique `Deal ID` (a dual-fuel contract appears as 2 rows: 1 Power deal + 1 Gas deal). |
| **Expected margin & Volume** | Sum of `Margin at signature (EUR)` and `Physical volume (MWh)` over the full contract duration. |
| **Unit margin (€/MWh) — Average** | Volume-weighted average: `Sum(Margin) / Sum(Physical volume)`. |
| **Unit margin (€/MWh) — Median** | Median of individual deal `Margin / Physical volume` on `Physical supply` offers with volume > 0. |
| **Active sales reps** | Unique `Sales rep ID` having signed at least one non-tacit deal during the period. |
""")
