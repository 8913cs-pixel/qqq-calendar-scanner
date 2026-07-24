import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

###################################################
# PAGE
###################################################

st.set_page_config(
    page_title="QQQ Triple Calendar Scanner",
    layout="wide"
)

st.title("QQQ Triple Calendar Scanner")

###################################################
# FUNCTIONS
###################################################

def round_strike(value, increment):
    return int(round(value / increment) * increment)

def option_price(df, strike):

    row = df[df["strike"] == strike]

    if len(row) == 0:
        return None

    price = float(row.iloc[0]["lastPrice"])

    if np.isnan(price):
        return None

    return price

###################################################
# LOAD QQQ
###################################################

ticker = yf.Ticker("QQQ")

hist = ticker.history(period="30d")

if hist.empty:
    st.error("Unable to retrieve QQQ data.")
    st.stop()

current_price = float(hist["Close"].iloc[-1])

st.metric(
    "QQQ Price",
    f"${current_price:.2f}"
)

###################################################
# SETTINGS
###################################################

col1, col2, col3 = st.columns(3)

with col1:
    strike_increment = st.selectbox(
        "Strike Increment",
        [5, 10],
        index=1
    )

with col2:
    cushion = st.number_input(
        "Cushion",
        min_value=0,
        value=0,
        step=5
    )

with col3:
    lookahead_exp = st.slider(
        "Back Expiration Position",
        1,
        8,
        3
    )

###################################################
# EXPIRATIONS
###################################################

expirations = ticker.options

if len(expirations) < 2:
    st.error("Not enough expirations found.")
    st.stop()

front_exp = expirations[0]

if lookahead_exp >= len(expirations):
    lookahead_exp = len(expirations) - 1

back_exp = expirations[lookahead_exp]

st.info(
    f"Front Exp: {front_exp} | Back Exp: {back_exp}"
)

###################################################
# OPTION CHAINS
###################################################

front_chain = ticker.option_chain(front_exp)
back_chain = ticker.option_chain(back_exp)

front_calls = front_chain.calls
front_puts = front_chain.puts

back_calls = back_chain.calls
back_puts = back_chain.puts

###################################################
# ATM
###################################################

atm = round_strike(
    current_price,
    strike_increment
)

###################################################
# ATM STRADDLE
###################################################

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
        f"Could not locate strike {atm}"
    )

    st.stop()

atm_straddle = atm_call + atm_put

###################################################
# DISTANCE
###################################################

distance = atm_straddle + cushion

distance = round_strike(
    distance,
    strike_increment
)

###################################################
# STRIKES
###################################################

lower_put = round_strike(
    atm - distance,
    strike_increment
)

upper_call = round_strike(
    atm + distance,
    strike_increment
)

###################################################
# STRUCTURE
###################################################

st.subheader("Primary Triple Calendar")

structure = pd.DataFrame({
    "Component": [
        "Lower Put Calendar",
        "ATM Put Calendar",
        "Upper Call Calendar"
    ],
    "Strike": [
        lower_put,
        atm,
        upper_call
    ]
})

st.dataframe(
    structure,
    use_container_width=True
)

###################################################
# DISPLAY STRADDLE
###################################################

col1,col2,col3,col4 = st.columns(4)

with col1:
    st.metric(
        "ATM Call",
        f"${atm_call:.2f}"
    )

with col2:
    st.metric(
        "ATM Put",
        f"${atm_put:.2f}"
    )

with col3:
    st.metric(
        "ATM Straddle",
        f"${atm_straddle:.2f}"
    )

with col4:
    st.metric(
        "Distance",
        distance
    )

###################################################
# DEBITS
###################################################

lower_front_put = option_price(
    front_puts,
    lower_put
)

lower_back_put = option_price(
    back_puts,
    lower_put
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
    upper_call
)

upper_back_call = option_price(
    back_calls,
    upper_call
)

if all([
    lower_front_put is not None,
    lower_back_put is not None,
    atm_front_put is not None,
    atm_back_put is not None,
    upper_front_call is not None,
    upper_back_call is not None
]):

    lower_debit = (
        lower_back_put -
        lower_front_put
    )

    atm_debit = (
        atm_back_put -
        atm_front_put
    )

    upper_debit = (
        upper_back_call -
        upper_front_call
    )

    total_debit = (
        lower_debit +
        atm_debit +
        upper_debit
    )

    summary = pd.DataFrame({
        "Calendar": [
            "Lower Put",
            "ATM Put",
            "Upper Call"
        ],
        "Debit": [
            round(lower_debit,2),
            round(atm_debit,2),
            round(upper_debit,2)
        ]
    })

    st.subheader("Debit Summary")

    st.dataframe(
        summary,
        use_container_width=True
    )

    st.metric(
        "Total Debit",
        f"${total_debit:.2f}"
    )

###################################################
# TRADE LEGS
###################################################

legs = pd.DataFrame({
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

st.subheader("Suggested Trade")

st.dataframe(
    legs,
    use_container_width=True
)

###################################################
# ALTERNATIVE SETUPS
###################################################

ideas = []

for center in range(
    atm - 30,
    atm + 35,
    strike_increment
):

    center = round_strike(
        center,
        strike_increment
    )

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
        center_straddle + cushion,
        strike_increment
    )

    lower = round_strike(
        center - spacing,
        strike_increment
    )

    upper = round_strike(
        center + spacing,
        strike_increment
    )

    ideas.append([
        center,
        spacing,
        lower,
        upper
    ])

ideas_df = pd.DataFrame(
    ideas,
    columns=[
        "ATM",
        "Spacing",
        "Put Calendar",
        "Call Calendar"
    ]
)

st.subheader(
    "Additional Triple Calendar Ideas"
)

st.dataframe(
    ideas_df,
    use_container_width=True
)

###################################################
# PAYOFF ZONE
###################################################

x = np.linspace(
    atm - distance * 2,
    atm + distance * 2,
    200
)

y = []

for price in x:

    score = (
        distance -
        abs(price - atm)
    )

    y.append(score)

chart_df = pd.DataFrame({
    "QQQ Price": x,
    "Relative Score": y
})

fig = px.line(
    chart_df,
    x="QQQ Price",
    y="Relative Score",
    title="Approximate Triple Calendar Zone"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

###################################################
# QQQ CHART
###################################################

st.subheader("QQQ Price Chart")

fig2 = px.line(
    hist,
    y="Close",
    title="QQQ Last 30 Days"
)

st.plotly_chart(
    fig2,
    use_container_width=True
)

###################################################
# REFRESH
###################################################

if st.button("Refresh"):
    st.rerun()

st.info(
    """
    Strategy Logic:

    ATM Straddle = ATM Call + ATM Put

    Distance = ATM Straddle + Cushion

    Triple Calendar:

    Lower Put Calendar

    ATM Put Calendar

    Upper Call Calendar

    All strikes rounded to chosen increment.
    """
)
