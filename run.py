import sys
from src.orchestrator.orchestrator import run

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Analyze ROAS drop in last 7 days"
    run(query)

    # Print a clean final message so the script is never silent
    print("\n✔ Pipeline complete.")
    print("✔ Insights, creatives, and report saved to: reports/")
    print(f"✔ Query processed: {query}\n")
