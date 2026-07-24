import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
import math
import plotly.express as px

st.set_page_config(
    page_title="QQQ Triple Calendar Pro",
    layout="wide"
)

##################################################
# FUNCTIONS
##################################################

def black_scholes_greeks(
    S,
    K,
    T,
    r,
    sigma,
    option_type="call"
):

    if T <= 0 or sigma <= 0:
        return None

    d1 = (
        np.log(S / K)
        + (r + sigma ** 2 / 2) * T
    ) / (sigma * np.sqrt(T))

    d2 = d1 - sigma * np.sqrt(T)

    if option_type == "call":
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    gamma = (
        norm.pdf(d1)
        / (S * sigma * np.sqrt(T))
    )

    vega = (
        S
        * norm.pdf(d1)
        * np.sqrt(T)
        / 100
    )

    theta = (
        -(
            S
            * norm.pdf(d1)
            * sigma
        )
        / (
            2
            * np.sqrt(T)
        )
    ) / 365

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta
    }


def expected_move(price, iv, dte):
    return price * iv * np.sqrt(dte / 365)


def option_price(df, strike):

    row = df[df["strike"] == strike]

    if len(row) == 0:
        return None

    return float(row.iloc[0]["lastPrice"])


def option_iv(df, strike):

    row = df[df["strike"] == strike]

    if len(row) == 0:
        return 0.25

    iv = float(row.iloc[0]["impliedVolatility"])

    if np.isnan(iv):
        return 0.25

    return iv


##################################################
# TITLE
##################################################

st.title("QQQ Triple Calendar Pro Scanner")

ticker = yf.Ticker("QQQ")

##################################################
# PRICE
##################################################

hist = ticker.history(period="30d")

price = float(hist["Close"].iloc[-1])

st.metric(
    "QQQ Current Price",
    f"${price:.2f}"
)

##################################################
# EXPIRATIONS
##################################################

expirations = ticker.options

if len(expirations) < 2:
    st.stop()

col1,col2 = st.columns(2)

with col1:
    front_exp = st.selectbox(
        "Front Expiration",
        expirations,
        0
    )

with col2:
    back_exp = st.selectbox(
        "Back Expiration",
        expirations,
        min(3,len(expirations)-1)
    )

if front_exp == back_exp:
    st.warning(
        "Choose different expirations"
    )
    st.stop()

##################################################
# CHAINS
##################################################

front_chain = ticker.option_chain(front_exp)
back_chain = ticker.option_chain(back_exp)

front_calls = front_chain.calls
back_calls = back_chain.calls

front_puts = front_chain.puts
back_puts = back_chain.puts

##################################################
# ATM
##################################################

strikes = front_calls["strike"].tolist()

atm = min(
    strikes,
    key=lambda x: abs(x-price)
)

st.subheader(
    f"ATM Strike: {atm}"
)

wing = st.slider(
    "Wing Width",
    5,
    25,
    10
)

lower = atm - wing
upper = atm + wing

##################################################
# CALENDAR DEBITS
##################################################

atm_front = option_price(
    front_calls,
    atm
)

atm_back = option_price(
    back_calls,
    atm
)

put_front = option_price(
    front_puts,
    lower
)

put_back = option_price(
    back_puts,
    lower
)

upper_front = option_price(
    front_calls,
    upper
)

upper_back = option_price(
    back_calls,
    upper
)

if None in [
    atm_front,
    atm_back,
    put_front,
    put_back,
    upper_front,
    upper_back
]:
    st.error(
        "Could not build strategy"
    )
    st.stop()

atm_debit = atm_back - atm_front
put_debit = put_back - put_front
upper_debit = upper_back - upper_front

total_debit = (
    atm_debit
    + put_debit
    + upper_debit
)

##################################################
# SUMMARY
##################################################

st.subheader("Strategy Summary")

summary = pd.DataFrame({
    "Component":[
        "ATM Calendar",
        "Put Calendar",
        "Call Calendar"
    ],
    "Debit":[
        round(atm_debit,2),
        round(put_debit,2),
        round(upper_debit,2)
    ]
})

st.dataframe(
    summary,
    use_container_width=True
)

st.metric(
    "Total Debit",
    f"${total_debit:.2f}"
)

##################################################
# IV / EXPECTED MOVE
##################################################

atm_iv = option_iv(
    front_calls,
    atm
)

em = expected_move(
    price,
    atm_iv,
    30
)

col1,col2 = st.columns(2)

with col1:
    st.metric(
        "ATM IV",
        f"{atm_iv*100:.2f}%"
    )

with col2:
    st.metric(
        "30-Day Expected Move",
        f"${em:.2f}"
    )

##################################################
# GREEKS
##################################################

T = 30/365
r = 0.04

greeks = black_scholes_greeks(
    price,
    atm,
    T,
    r,
    atm_iv,
    "call"
)

if greeks:

    st.subheader("ATM Greeks")

    gdf = pd.DataFrame({
        "Greek":[
            "Delta",
            "Gamma",
            "Vega",
            "Theta"
        ],
        "Value":[
            round(greeks["delta"],4),
            round(greeks["gamma"],4),
            round(greeks["vega"],4),
            round(greeks["theta"],4)
        ]
    })

    st.dataframe(
        gdf,
        use_container_width=True
    )

##################################################
# SCANNER
##################################################

st.subheader(
    "Top Calendar Opportunities"
)

results = []

for strike in front_calls["strike"]:

    front_row = front_calls[
        front_calls["strike"] == strike
    ]

    back_row = back_calls[
        back_calls["strike"] == strike
    ]

    if (
        len(front_row)==0
        or len(back_row)==0
    ):
        continue

    fp = float(
        front_row.iloc[0]["lastPrice"]
    )

    bp = float(
        back_row.iloc[0]["lastPrice"]
    )

    iv = float(
        front_row.iloc[0][
            "impliedVolatility"
        ]
    )

    if np.isnan(iv):
        iv = 0.20

    debit = bp - fp

    if debit <= 0:
        continue

    distance = abs(
        strike-price
    )

    score = (
        (iv*100)
        /
        (debit+0.01)
    )

    results.append([
        strike,
        round(debit,2),
        round(iv*100,2),
        round(distance,2),
        round(score,2)
    ])

scanner = pd.DataFrame(
    results,
    columns=[
        "Strike",
        "Debit",
        "IV %",
        "Distance",
        "Score"
    ]
)

scanner = scanner.sort_values(
    "Score",
    ascending=False
)

st.dataframe(
    scanner.head(20),
    use_container_width=True
)

##################################################
# BEST IDEA
##################################################

best = scanner.iloc[0]

st.subheader(
    "Best Trade Candidate"
)

st.success(
    f"""
    Strike: {best['Strike']}
    
    Estimated Debit: ${best['Debit']}
    
    Opportunity Score: {best['Score']}
    """
)

##################################################
# PAYOFF VISUAL
##################################################

x = np.linspace(
    price-50,
    price+50,
    150
)

payoff = []

for p in x:

    zone_reward = (
        15
        -
        abs(
            p-float(best["Strike"])
        )
        / 3
    )

    pnl = (
        zone_reward
        - float(best["Debit"])
    )

    payoff.append(pnl)

chart = pd.DataFrame({
    "QQQ Price":x,
    "P/L":payoff
})

fig = px.line(
    chart,
    x="QQQ Price",
    y="P/L",
    title="Approximate Calendar Profit Zone"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

##################################################
# CONTRACTS
##################################################

st.subheader(
    "Suggested Triple Calendar"
)

contracts = pd.DataFrame({
    "Leg":[
        "Buy Back ATM Call",
        "Sell Front ATM Call",
        "Buy Back Lower Put",
        "Sell Front Lower Put",
        "Buy Back Upper Call",
        "Sell Front Upper Call"
    ],
    "Strike":[
        atm,
        atm,
        lower,
        lower,
        upper,
        upper
    ]
})

st.dataframe(
    contracts,
    use_container_width=True
)

##################################################
# CHART
##################################################

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

##################################################
# REFRESH
##################################################

if st.button("Refresh Data"):
    st.rerun()

st.info(
"""
Educational use only.

Verify pricing, liquidity,
bid/ask spreads,
margin requirements,
and risk before trading.
"""
)
