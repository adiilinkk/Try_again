import sys
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
load_dotenv('config/secrets.env')
IST = pytz.timezone('Asia/Kolkata')
def separator(title):
    print()
    print('=' * 50)
    print(f'  {title}')
    print('=' * 50)
def run_all_tests():

    # ─────────────────────────────────────
    # TEST 1: NSE NIFTY 50
    # ─────────────────────────────────────
    separator('TEST 1: NSE NIFTY 50')
    try:
        from data.fetchers.nse_data import (
            fetch_nifty_data
        )
        result = fetch_nifty_data()
        nifty = result.get('nifty50')
        banknifty = result.get('banknifty')

        if nifty:
            arrow = '▲' if nifty.change_pct >= 0 else '▼'
            print(f'Nifty 50 Price:    {nifty.value:>10,.2f}')
            print(f'Change:            {arrow} {abs(nifty.change_pct):.2f}%')
            print(f'Prev Close:        {result.get("nifty50_prev", "N/A"):>10}')
            print(f'Data Source:       {nifty.source}')
            print(f'Data Age:          {nifty.age_minutes():.1f} minutes old')
            print(f'STATUS: PASS ✅')
        else:
            print('Nifty 50: No data returned')
            print('Note: NSE APIs return limited')
            print('data outside market hours.')
            print('Test between 9AM-3:30PM IST')
            print('STATUS: INCONCLUSIVE ⚠️')

        if banknifty:
            arrow = '▲' if banknifty.change_pct >= 0 else '▼'
            print()
            print(f'Bank Nifty Price:  {banknifty.value:>10,.2f}')
            print(f'Change:            {arrow} {abs(banknifty.change_pct):.2f}%')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 2: NSE FII/DII
    # ─────────────────────────────────────
    separator('TEST 2: NSE FII/DII DATA')
    try:
        from data.fetchers.nse_data import fetch_fii_dii
        result = fetch_fii_dii()

        if result.get('fii_net') is not None:
            fii = result['fii_net']
            dii = result['dii_net']
            date = result['date']

            fii_dir = 'NET BUY 🟢' if fii > 0 else 'NET SELL 🔴'
            dii_dir = 'NET BUY 🟢' if dii > 0 else 'NET SELL 🔴'

            print(f'Date:              {date}')
            print(f'FII Activity:      {fii_dir}')
            print(f'FII Net:           Rs {abs(fii):>10,.2f} Cr')
            print(f'DII Activity:      {dii_dir}')
            print(f'DII Net:           Rs {abs(dii):>10,.2f} Cr')
            print(f'Source:            {result["source"]}')
            print(f'STATUS: PASS ✅')
        else:
            print('FII/DII data not available')
            print('NSE publishes this by 6 PM daily')
            print('STATUS: INCONCLUSIVE ⚠️')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 3: NSE TOP MOVERS
    # ─────────────────────────────────────
    separator('TEST 3: NSE TOP MOVERS')
    try:
        from data.fetchers.nse_data import (
            fetch_top_movers
        )
        result = fetch_top_movers()
        gainers = result.get('gainers', [])
        losers = result.get('losers', [])

        if gainers:
            print('TOP GAINERS:')
            for i, g in enumerate(gainers[:5], 1):
                print(
                    f'  {i}. {g["symbol"]:<15} '
                    f'+{g["pChange"]:.1f}%  '
                    f'Rs {g["ltp"]:,.2f}'
                )
        else:
            print('No gainers data (market closed)')

        print()

        if losers:
            print('TOP LOSERS:')
            for i, l in enumerate(losers[:5], 1):
                print(
                    f'  {i}. {l["symbol"]:<15} '
                    f'{l["pChange"]:.1f}%  '
                    f'Rs {l["ltp"]:,.2f}'
                )
        else:
            print('No losers data (market closed)')

        if gainers or losers:
            print(f'STATUS: PASS ✅')
        else:
            print('STATUS: INCONCLUSIVE ⚠️')
            print('Test during market hours')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 4: BSE SENSEX
    # ─────────────────────────────────────
    separator('TEST 4: BSE SENSEX')
    try:
        from data.fetchers.nse_data import fetch_sensex
        sensex = fetch_sensex()

        if sensex and sensex.value > 0:
            arrow = '▲' if sensex.change_pct >= 0 else '▼'
            print(f'Sensex Price:      {sensex.value:>10,.2f}')
            print(f'Change:            {arrow} {abs(sensex.change_pct):.2f}%')
            print(f'Source:            {sensex.source}')
            print(f'STATUS: PASS ✅')
        else:
            print('Sensex data not available')
            print('STATUS: INCONCLUSIVE ⚠️')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 5: GLOBAL MARKETS (yfinance)
    # ─────────────────────────────────────
    separator('TEST 5: GLOBAL MARKETS (yfinance)')
    try:
        from data.fetchers.global_markets import (
            fetch_all_global_markets,
            classify_vix
        )
        markets = fetch_all_global_markets()

        indices = {
            'sp500':     'S&P 500    ',
            'nasdaq':    'Nasdaq     ',
            'dow':       'Dow Jones  ',
            'vix':       'VIX        ',
            'nikkei':    'Nikkei     ',
            'hang_seng': 'Hang Seng  ',
        }

        passed = 0
        for key, label in indices.items():
            dp = markets.get(key)
            if dp and dp.value > 0:
                arrow = '▲' if dp.change_pct >= 0 else '▼'
                print(
                    f'{label}: {dp.value:>10,.2f}  '
                    f'{arrow} {abs(dp.change_pct):.2f}%'
                )
                passed += 1
            else:
                print(f'{label}: ❌ Failed')

        vix_dp = markets.get('vix')
        if vix_dp:
            print()
            print(f'VIX Sentiment:     {classify_vix(vix_dp.value)}')

        print()
        print(f'Fetched: {passed}/{len(indices)} indices')
        if passed >= 4:
            print('STATUS: PASS ✅')
        else:
            print('STATUS: PARTIAL ⚠️')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 6: GIFT NIFTY PROXY
    # ─────────────────────────────────────
    separator('TEST 6: GIFT NIFTY (yfinance proxy)')
    try:
        from data.fetchers.global_markets import (
            fetch_all_global_markets
        )
        from data.fetchers.gift_nifty import (
            fetch_gift_nifty,
            calculate_gap
        )

        gift = fetch_gift_nifty()

        if gift and gift.value > 0:
            print(f'Gift Nifty Value:  {gift.value:>10,.2f}')
            print(f'Is Indicative:     {gift.is_indicative}')
            print(f'Confidence:        {gift.confidence:.2f}')
            print(f'Source:            {gift.source}')

            markets = fetch_all_global_markets()
            nifty_prev = 24000

            gap_pts, gap_pct, direction = calculate_gap(
                gift.value, nifty_prev
            )
            print()
            print(f'Gap vs 24000:      {gap_pts:+.2f} pts')
            print(f'Gap Percent:       {gap_pct:+.2f}%')
            print(f'Direction:         {direction}')
            print(f'STATUS: PASS ✅')
        else:
            print('Gift Nifty proxy failed')
            print('STATUS: FAIL ❌')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 7: NEWS API
    # ─────────────────────────────────────
    separator('TEST 7: NEWS API')
    try:
        from data.fetchers.news import fetch_news

        headlines = fetch_news(hours_back=24)

        if headlines:
            print(f'Headlines fetched: {len(headlines)}')
            print()
            print('LATEST HEADLINES:')
            for i, h in enumerate(headlines[:5], 1):
                title = h["title"][:60]
                source = h["source"]
                print(f'  {i}. [{source}]')
                print(f'     {title}...')
                print()
            print(f'STATUS: PASS ✅')
        else:
            print('No headlines returned')
            print('Check NEWS_API_KEY in secrets.env')
            print('STATUS: FAIL ❌')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 8: CLAUDE AI API
    # ─────────────────────────────────────
    separator('TEST 8: CLAUDE AI API')
    try:
        import anthropic

        api_key = os.getenv('ANTHROPIC_API_KEY')

        if not api_key or 'update' in api_key.lower():
            print('ANTHROPIC_API_KEY not set')
            print('Get key from console.anthropic.com')
            print('STATUS: SKIP ⏭️')
        else:
            client = anthropic.Anthropic(
                api_key=api_key
            )

            message = client.messages.create(
                model='claude-sonnet-4-5',
                max_tokens=150,
                messages=[{
                    'role': 'user',
                    'content': (
                        'You are a financial data formatter. '
                        'Convert this data to one line: '
                        'Nifty 50 is at 24108, '
                        'up 0.43% today.'
                    )
                }]
            )

            response = message.content[0].text
            print(f'AI Response:')
            print(f'  {response}')
            print()
            print(f'Model used: claude-sonnet-4-5')
            print(f'Tokens used: {message.usage.input_tokens} in, '
                  f'{message.usage.output_tokens} out')
            print(f'STATUS: PASS ✅')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # TEST 9: MARKET STATUS
    # ─────────────────────────────────────
    separator('TEST 9: NSE MARKET STATUS')
    try:
        from data.fetchers.nse_data import (
            fetch_market_status
        )

        status = fetch_market_status()
        now_ist = datetime.now(IST)

        print(f'Current IST Time:  {now_ist.strftime("%I:%M %p")}')
        print(f'Market Status:     {status.upper()}')

        if status == 'open':
            print('Market is OPEN right now')
        elif status == 'pre-open':
            print('Pre-open session active (9:00-9:15 AM)')
        else:
            print('Market is CLOSED')
            print('Live data limited outside market hours')
        print(f'STATUS: PASS ✅')

    except Exception as e:
        print(f'STATUS: FAIL ❌')
        print(f'Error: {e}')
    # ─────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────
    separator('FINAL SUMMARY')
    print()
    print('Cross-check these numbers manually:')
    print('→ Nifty 50: Check on nseindia.com')
    print('→ S&P 500:  Check on finance.yahoo.com')
    print('→ FII/DII:  Check on nseindia.com/web/nse/FII-DII-activity')
    print('→ VIX:      Check on finance.yahoo.com (^VIX)')
    print()
    print('If numbers match → data is accurate ✅')
    print('If numbers differ → check API source ⚠️')
    print()
    now = datetime.now(IST)
    print(f'Test completed at: {now.strftime("%d %b %Y %I:%M %p IST")}')
if __name__ == '__main__':
    run_all_tests()
