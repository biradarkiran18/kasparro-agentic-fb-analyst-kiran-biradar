from src.orchestrator.orchestrator import run
import sys
import yaml


def main():
    # Load config
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Get data path from config or command line
    data_path = config.get("data_csv", "data/sample_fb_ads.csv")
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    
    print(f"🚀 Running V2 Pipeline on: {data_path}")
    print("=" * 60)
    
    # Run the orchestrator (returns dict with all outputs)
    result = run(data_path, config=config)
    
    print("\n✅ Pipeline complete!")
    print("=" * 60)
    print(f"📊 Validated Insights: {result['metrics']['num_passed']}/{result['metrics']['num_hypotheses']}")
    print(f"💡 Creative Bundles Generated: {len(result['creatives'])}")
    print(f"📈 Validation Rate: {result['metrics']['validation_rate']:.1%}")
    print(f"\n📁 Outputs saved to:")
    print(f"   - reports/insights.json")
    print(f"   - reports/creatives.json")
    print(f"   - reports/metrics.json")
    print(f"   - logs/observability/ (detailed execution logs)")
    
    if result.get("drift", {}).get("drift"):
        print(f"\n⚠️  Schema drift detected!")
        print(f"   See reports/drift_report.json for details")


if __name__ == "__main__":
    main()
