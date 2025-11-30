# Self-Review

This document summarizes the choices I made while building the project, what I focused on, and what I would improve if I had more time.

## 1. What the project does
The project loads a Facebook Ads dataset, summarizes the numbers, forms basic hypotheses about performance changes, checks those hypotheses against the data, and then generates simple creative suggestions for low-CTR campaigns. The flow is organized across separate modules to keep things understandable and maintainable.

## 2. Design decisions

### a. Keep things local and simple  
I designed everything to run offline. There are no external API calls. All logic is inside pure Python modules. This keeps the behavior stable and easy to test.

### b. Use small, clear modules  
I separated logic into:
- data loading and summary  
- hypothesis creation  
- validation  
- creative suggestion  
- an orchestrator to connect all of them  

This makes it easy to test each part individually.

### c. Prefer explicit rules  
Instead of relying on ML models or unpredictable logic, I used straightforward rules:
- CTR thresholds  
- ROAS comparisons  
- confidence adjustments  
These are clear, easy to verify, and behave consistently.

### d. Add basic logging  
Each major step writes a short log entry to help understand what happened in a run.  
This keeps the pipeline easy to debug without introducing heavy tooling.

### e. Keep tests simple and meaningful  
I wrote tests that check:
- data summarization  
- hypothesis evaluation  
- creative generation  
- basic orchestration  
These give confidence that the core pieces work as expected.

## 3. What could be improved later

### a. Broader hypothesis coverage  
Right now the hypotheses focus mainly on ROAS changes and creative fatigue.  
More conditions (cost spikes, impression drops, etc.) could be added.

### b. More flexible thresholds  
The thresholds are static. They could be adjusted based on recent averages or moving windows.

### c. More detailed reporting  
The current reports are useful, but adding short explanations or comparisons (e.g., week-over-week changes) would help make the output more informative.

### d. Better log organization  
Logs work fine but could benefit from timestamps grouped by run or a cleaner naming pattern.

## 4. Summary
The project is stable, readable, and test-covered.  
It performs the intended analysis consistently.  
If extended, I would focus on expanding hypothesis logic, improving reporting depth, and refining the logging layout.