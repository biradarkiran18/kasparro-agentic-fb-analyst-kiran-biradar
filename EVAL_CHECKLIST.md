# Evaluation Checklist

This checklist summarizes how the project was built and what is included.

## 1. Structure
- Clear folder layout  
- Separate modules for data work, hypothesis logic, validation, and reporting  
- Orchestrator coordinates everything  
- Tests stored in a dedicated folder  

## 2. Data handling
- Loads CSV safely  
- Handles missing columns (e.g., purchases)  
- Computes ROAS and CTR when missing  
- Summaries include global metrics and campaign-level metrics  

## 3. Hypothesis generation
- Generates a small set of straightforward hypotheses  
- Uses actual data patterns such as ROAS changes and low CTR  
- Includes confidence values that can later be refined  

## 4. Validation logic
- Checks hypotheses with simple comparisons  
- Supports threshold adjustments  
- Produces final confidence and notes  
- Tested against malformed and empty inputs  

## 5. Creative suggestions
- Identifies campaigns with low CTR  
- Generates simple text suggestions  
- Keeps output deterministic and readable  

## 6. Orchestration
- Runs all steps in sequence  
- Writes results to JSON files  
- Generates a short human-readable report  
- Saves logs for understanding run history  

## 7. Logging
- Each major step writes a log entry  
- Logs include timestamps and basic metadata  
- All logs stored in a single folder for simplicity  

## 8. Tests
- Covers data loading  
- Covers summary calculations  
- Covers hypothesis evaluation  
- Covers creative generation  
- Includes a small end-to-end run test  
- All tests pass  

## 9. Reproducibility
- No external network calls  
- Static thresholds in config  
- Results fully determined by input CSV  
- Requirements pinned to specific versions  

## 10. What can be improved
- Expand test coverage for unusual datasets  
- Add more hypothesis types  
- Improve explanations in the generated report  
- Add optional configuration for thresholds or filters  