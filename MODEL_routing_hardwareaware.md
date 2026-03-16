# DVA Wizard v3.0 - Hardware-Aware Model Routing



33 seconds for the response time was determined quite slow. Review the analsysis below where previous work was done to check the hardware and identify the bottleneck (there is no need to modify or run any code - just be aware of the history of troubleshooting):

```shell
$ docker exec dva-db psql -U postgres -d dva_db -c "SELECT COUNT(*) FROM scraped_content;" 2>&1

 count 
-------
  5305
(1 row)
```

```shell
$ docker exec dva-ollama ollama list 2>&1

NAME                        ID              SIZE      MODIFIED    
qwen2.5:7b                  845dbda0ea48    4.7 GB    4 hours ago    
codellama:7b                8fdf8f752f6e    3.8 GB    4 hours ago    
qwen2.5:14b                 7cdf5a0187d5    9.0 GB    4 hours ago    
mxbai-embed-large:latest    468836162de7    669 MB    4 hours ago    
llama3.1:8b                 46e0c10c039e    4.9 GB    5 hours ago    
```

Analysis:

Factor Status
GPU GTX 1060 6GB (older/weak)
VRAM Used 92% (5647/6144 MiB) - Critical!
qwen2.5:14b 9GB - Won't fit in 6GB!
Root Cause: The 9GB qwen2.5:14b model doesn't fit in your 6GB VRAM alongside embeddings. This forces GPU swapping to system RAM → massive slowdown.

## Solutions

Switch to smaller models (recommended):
Use llama3.1:8b (4.9GB) or qwen2.5:7b (4.7GB) instead of 14b
Reduce embeddings in memory - fewer vector search results

Two options were presented:

Option A: Change default model to llama3.1:8b in .env
Option B: Adjust model routing to use smaller models on this hardware

### Implications, benefits and downsides of option a vs option b

**Option A: Change Default Model to llama3.1:8b**

Implications All queries route to 8b model unless explicitly overridden

Benefits Consistent, reliable, won't OOM, ~50% faster than 14b

Downsides Less capable for complex reasoning tasks, 14b is smarter

**Option B: Adjust Model Routing Based on Hardware**
Implications Smart routing - simple queries use 8b, complex use 14b if VRAM available
Benefits Best of both worlds - fast for simple, capable for complex
Downsides More complex code, potential for 14b to fail if routing logic isn't perfect

### Recommendation: Option B

With hardware-aware routing:

Simple query → llama3.1:8b (~5-10s)
Complex query → qwen2.5:14b if VRAM > 3GB free, else 8b
This gives you:

* Fast responses for basic questions
* Capability for complex reasoning when hardware allows
* No crashes from OOM

Based on the validity of the above analysis, implement Option B with hardware-aware model routing.
