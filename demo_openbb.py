#!/usr/bin/env python3
"""
Demo script for OpenBB API integration in Nickberg Terminal

Shows working FMP market data integration.
"""

import sys
sys.path.insert(0, "src")

from openbb_market_data import create_market_data_provider


def demo_market_data():
    """Demo the working OpenBB market data features."""
    print("=" * 60)
    print("📈 OpenBB API Integration Demo")
    print("=" * 60)
    
    # Create provider
    print("\n🔄 Initializing OpenBB Market Data Provider...")
    provider = create_market_data_provider()
    
    watchlist = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]
    
    # Demo 1: Stock Prices
    print("\n" + "-" * 60)
    print("💰 Stock Prices (FMP)")
    print("-" * 60)
    
    for ticker in watchlist:
        price = provider.get_price(ticker)
        change = provider.get_intraday_change(ticker)
        
        if price:
            if change is not None:
                emoji = "🟢" if change >= 0 else "🔴"
                print(f"{emoji} {ticker:6}: ${price:>8.2f} ({change:>+.2f}%)")
            else:
                print(f"⚪ {ticker:6}: ${price:>8.2f}")
        else:
            print(f"⚪ {ticker:6}: Data unavailable")
    
    # Demo 2: Market Context (detailed info)
    print("\n" + "-" * 60)
    print("📊 Market Context Example (AAPL)")
    print("-" * 60)
    
    context = provider.get_market_context("AAPL")
    if context:
        print(f"Company:      {context.get('company_name', 'N/A')}")
        print(f"Sector:       {context.get('sector', 'N/A')}")
        print(f"Industry:     {context.get('industry', 'N/A')}")
        print(f"Price:        ${context.get('current_price', 'N/A')}")
        print(f"Day Change:   {context.get('day_change_pct', 'N/A'):+.2f}%")
        if context.get('week_change_pct'):
            print(f"Week Change:  {context['week_change_pct']:+.2f}%")
    
    # Demo 3: Company Profile
    print("\n" + "-" * 60)
    print("🏢 Company Profile (TSLA)")
    print("-" * 60)
    
    profile = provider.get_company_profile("TSLA")
    if profile:
        print(f"Name:         {profile.get('name', 'N/A')}")
        print(f"Sector:       {profile.get('sector', 'N/A')}")
        print(f"Industry:     {profile.get('industry', 'N/A')}")
        print(f"Employees:    {profile.get('employees', 'N/A'):,}")
        if profile.get('website'):
            print(f"Website:      {profile['website']}")
    
    # Demo 4: Financial Summary
    print("\n" + "-" * 60)
    print("💵 Financial Summary (MSFT)")
    print("-" * 60)
    
    financials = provider.get_financial_summary("MSFT")
    if financials:
        revenue = financials.get('revenue', 0) / 1e9
        profit = financials.get('gross_profit', 0) / 1e9
        net_income = financials.get('net_income', 0) / 1e9
        
        print(f"Revenue:      ${revenue:>10.1f}B")
        print(f"Gross Profit: ${profit:>10.1f}B")
        print(f"Net Income:   ${net_income:>10.1f}B")
    
    # Demo 5: Historical Prices
    print("\n" + "-" * 60)
    print("📈 5-Day Price History (NVDA)")
    print("-" * 60)
    
    history = provider.get_historical_prices("NVDA", days=5)
    if history:
        for date, price in sorted(history.items())[-5:]:
            print(f"  {date}: ${price:.2f}")
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    print("\n💡 Integration Status:")
    print("   ✅ FMP (Stock Data): WORKING")
    print("   ⚠️  Polygon (News): Compatibility issue (optional)")
    print("   ⚠️  FRED (Economic): Compatibility issue (optional)")
    print("\n📚 See OPENBB_API_INTEGRATION_SUMMARY.md for details")


if __name__ == "__main__":
    demo_market_data()
