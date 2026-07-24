import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(
        interval=120000,
        key="refresh"
    )
except:
    pass

st.set_page_config(
    page_title="QQQ Triple Calendar Scanner",
    layout="wide"
)

st.title("QQQ Triple Calendar Scanner")

# ====================================
# FUNCTIONS
# ====================================

def round_strike(price):
    return int(round(price / 5) * 5)


def option_price(df, strike):

    row = df[df["strike"] == strike]

    if len(row) == 0:
        return None

    price = row.iloc[0]["lastPrice"]

    if pd.isna(price):
        return None

    return float(price)


def calculate_debit(
    front_calls,
    front_puts,
    back_calls,
    back_puts,
    lower,
    atm,
    upper
):

    lower_front_put = option_price(
        front_puts,
        lower
    )

    lower_back_put = option_price(
        back_puts,
        lower
    )

    atm_front_put = option_price(
        front_puts,
        atm
    )

    atm_back_put = option_price(
        back_puts,
        atm
    )

    upper_front_call = option_price(
        front_calls,
        upper
    )

    upper_back_call = option_price(
        back_calls,
        upper
    )

    prices = [
        lower_front_put,
        lower_back_put,
        atm_front_put,
        atm_back_put,
        upper_front_call,
        upper_back_call
    ]

    if any(x is None for x in prices):
        return None

    debit = (
        (lower_back_put - lower_front_put)
        +
        (atm_back_put - atm_front_put)
        +
        (upper_back_call - upper_front_call)
    )

    return round(debit, 2)


def build_payoff_chart(
    atm,
    distance,
    debit
):

    x = np.linspace(
        atm - distance * 2,
        atm + distance * 2,
        250
    )

    y = []

    for p in x:

        pnl = (
            distance
            - abs(p - atm)
        )

        pnl = pnl - debit

        y.append(pnl)

    chart_df = pd.DataFrame({
        "Price": x,
        "PnL": y
    })

    fig = px.line(
        chart_df,
        x="Price",
        y="PnL",
        title="Estimated Triple Calendar Payoff"
    )

    return fig


# ====================================
# LOAD DATA
# ====================================

ticker = yf.Ticker("QQQ")

hist = ticker.history(
    period="30d"
)

if hist.empty:

    st.error(
        "Unable to retrieve QQQ data."
    )

    st.stop()

current_price = float(
    hist["Close"].iloc[-1]
)

st.metric(
    "QQQ Price",
    f"${current_price:.2f}"
)

# ====================================
# EXPIRATIONS
# ====================================

expirations = ticker.options

if len(expirations) < 2:

    st.error(
        "No expiration data available."
    )

    st.stop()

col1, col2, col3 = st.columns(3)

with col1:

    near_exp = st.selectbox(
        "Near Expiration",
        expirations,
        index=0
    )

with col2:

    far_exp = st.selectbox(
        "Far Expiration",
        expirations,
        index=min(3, len(expirations)-1)
    )

with col3:

    cushion = st.number_input(
        "Cushion",
        value=5,
        min_value=0,
        step=5
    )

if near_exp == far_exp:

    st.warning(
        "Near and Far expirations must be different."
    )

    st.stop()

# ====================================
# OPTION CHAINS
# ====================================

front_chain = ticker.option_chain(
    near_exp
)

back_chain = ticker.option_chain(
    far_exp
)

front_calls = front_chain.calls
front_puts = front_chain.puts

back_calls = back_chain.calls
back_puts = back_chain.puts

# ====================================
# ATM STRADDLE
# ====================================

atm = round_strike(
    current_price
)

atm_call = option_price(
    front_calls,
    atm
)

atm_put = option_price(
    front_puts,
    atm
)

if atm_call is None or atm_put is None:

    st.error(
        f"Could not find ATM strike {atm}"
    )

    st.stop()

atm_straddle = (
    atm_call +
    atm_put
)

distance = round_strike(
    atm_straddle + cushion
)

lower_put = round_strike(
    atm - distance
)

upper_call = round_strike(
    atm + distance
)

main_debit = calculate_debit(
    front_calls,
    front_puts,
    back_calls,
    back_puts,
    lower_put,
    atm,
    upper_call
)

# ====================================
# MAIN SETUP
# ====================================

st.subheader(
    "Primary Triple Calendar"
)

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric(
    "ATM Strike",
    atm
)

m2.metric(
    "ATM Call",
    f"${atm_call:.2f}"
)

m3.metric(
    "ATM Put",
    f"${atm_put:.2f}"
)

m4.metric(
    "ATM Straddle",
    f"${atm_straddle:.2f}"
)

m5.metric(
    "Distance",
    distance
)

structure = pd.DataFrame({
    "Calendar":[
        "Lower Put Calendar",
        "ATM Put Calendar",
        "Upper Call Calendar"
    ],
    "Strike":[
        lower_put,
        atm,
        upper_call
    ]
})

st.dataframe(
    structure,
    use_container_width=True
)
if main_debit is not None:

    st.metric(
        "Primary Setup Debit",
        f"${main_debit:.2f}"
    )

trade_legs = pd.DataFrame({
    "Action": [
        "BUY BACK PUT",
        "SELL FRONT PUT",

        "BUY BACK PUT",
        "SELL FRONT PUT",

        "BUY BACK CALL",
        "SELL FRONT CALL"
    ],
    "Strike": [
        lower_put,
        lower_put,

        atm,
        atm,

        upper_call,
        upper_call
    ]
})

st.subheader(
    "Trade Legs"
)

st.dataframe(
    trade_legs,
    use_container_width=True
)

# ====================================
# ALTERNATIVE SETUPS
# ====================================

ideas = []

for center in range(
    atm - 50,
    atm + 55,
    5
):

    center_call = option_price(
        front_calls,
        center
    )

    center_put = option_price(
        front_puts,
        center
    )

    if (
        center_call is None
        or center_put is None
    ):
        continue

    center_straddle = (
        center_call +
        center_put
    )

    spacing = round_strike(
        center_straddle + cushion
    )

    lower = round_strike(
        center - spacing
    )

    upper = round_strike(
        center + spacing
    )

    debit = calculate_debit(
        front_calls,
        front_puts,
        back_calls,
        back_puts,
        lower,
        center,
        upper
    )

    if debit is None:
        continue

    ideas.append({
        "ATM": center,
        "Distance": spacing,
        "Lower": lower,
        "Upper": upper,
        "Debit": debit
    })

if len(ideas) == 0:

    st.error(
        "No valid calendar structures found."
    )

    st.stop()

ideas_df = pd.DataFrame(
    ideas
)

ideas_df = ideas_df.sort_values(
    "Debit",
    ascending=True
)

# ====================================
# BEST SETUP
# ====================================

best = ideas_df.iloc[0]

st.subheader(
    "🏆 Cheapest Triple Calendar"
)

st.success(
    f"""
Lower Put Calendar = {best['Lower']}

ATM Put Calendar = {best['ATM']}

Upper Call Calendar = {best['Upper']}

Distance = {best['Distance']}

Debit = ${best['Debit']}
"""
)

# ====================================
# BEST TRADE TICKET
# ====================================

st.code(
f"""
BUY {far_exp} {int(best['Lower'])} PUT
SELL {near_exp} {int(best['Lower'])} PUT

BUY {far_exp} {int(best['ATM'])} PUT
SELL {near_exp} {int(best['ATM'])} PUT

BUY {far_exp} {int(best['Upper'])} CALL
SELL {near_exp} {int(best['Upper'])} CALL
"""
)

# ====================================
# BEST PAYOFF CHART
# ====================================

best_chart = build_payoff_chart(
    best["ATM"],
    best["Distance"],
    best["Debit"]
)

best_chart.update_layout(
    title=f"Best Setup {best['Lower']}-{best['ATM']}-{best['Upper']}"
)

st.plotly_chart(
    best_chart,
    use_container_width=True,
    key="best_chart"
)

# ====================================
# ALL IDEAS
# ====================================

st.subheader(
    "Ranked Triple Calendar Ideas"
)

rank = 1

for idx, row in ideas_df.iterrows():

    title = (
        f"#{rank} | "
        f"Debit ${row['Debit']} | "
        f"{row['Lower']}P / "
        f"{row['ATM']}P / "
        f"{row['Upper']}C"
    )

    with st.expander(title):

        st.write(
            f"Lower Put Calendar: {row['Lower']}"
        )

        st.write(
            f"ATM Put Calendar: {row['ATM']}"
        )

        st.write(
            f"Upper Call Calendar: {row['Upper']}"
        )

        st.write(
            f"Distance: {row['Distance']}"
        )

        st.write(
            f"Total Debit: ${row['Debit']}"
        )

        ticket = f"""
BUY {far_exp} {int(row['Lower'])} PUT
SELL {near_exp} {int(row['Lower'])} PUT

BUY {far_exp} {int(row['ATM'])} PUT
SELL {near_exp} {int(row['ATM'])} PUT

BUY {far_exp} {int(row['Upper'])} CALL
SELL {near_exp} {int(row['Upper'])} CALL
"""

        st.code(ticket)

        payoff_chart = build_payoff_chart(
            row["ATM"],
            row["Distance"],
            row["Debit"]
        )

        payoff_chart.update_layout(
            title=(
                f"Payoff "
                f"{row['Lower']}P-"
                f"{row['ATM']}P-"
                f"{row['Upper']}C"
            )
        )

        st.plotly_chart(
            payoff_chart,
            use_container_width=True,
            key=f"chart_{rank}_{row['ATM']}_{row['Lower']}_{row['Upper']}"
        )

    rank += 1
    
# ====================================
# TABLE OF ALL SETUPS
# ====================================

st.subheader(
    "Setup Comparison"
)

st.dataframe(
    ideas_df,
    use_container_width=True
)

# ====================================
# QQQ CHART
# ====================================

st.subheader(
    "QQQ Last 30 Days"
)

fig_price = px.line(
    hist,
    y="Close",
    title="QQQ Price History"
)

st.plotly_chart(
    fig_price,
    use_container_width=True
)

# ====================================
# REFRESH
# ====================================

if st.button(
    "Refresh Now"
):
    st.rerun()

st.info(
    f"""
Near Expiration: {near_exp}

Far Expiration: {far_exp}

Logic:

ATM Put Calendar

Lower Put Calendar

Upper Call Calendar

Distance =
ATM Straddle + Cushion

Suggestions are ranked by
lowest total debit.
"""
)
