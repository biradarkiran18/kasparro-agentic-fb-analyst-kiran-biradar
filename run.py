from src.orchestrator.orchestrator import run
import sys

def main():
    query = "Analyze ROAS drop in last 7 days"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    validated, creatives = run(query)
    print("✔ Pipeline complete.")
    print("✔ Insights, creatives, and report saved to: reports/")
    print(f"✔ Query processed: {query}")

if __name__ == "__main__":
    main()