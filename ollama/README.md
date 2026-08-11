# Ollama in the AI Lab

Ollama is the initial, simplest local model runtime. It is not the lab's model abstraction or its permanent model strategy.

## Recommended first approach: native on the T480 host

Run Ollama natively when first exploring CPU-only inference. It makes model management and host-level inspection simple. Docker applications can reach it through an explicitly configured endpoint; on Linux, a reliable option is to publish Ollama deliberately on the T480's private interface or use a host-gateway mapping for the application container. Do not assume `localhost` inside a container means the host.

## Alternative: Docker Compose profile

The root Compose file includes an optional `ollama` profile:

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull <chosen-model>
```

This keeps model files in the `ollama_models` named volume and makes the service available to other Compose services at `http://ollama:11434`. It is isolated and portable, but native host operation is the more straightforward initial learning path.

## T480 expectations

The 32 GB RAM, CPU-only T480 is best for small, quantised models and embedding workloads. Start with roughly 2–8B parameter models in a suitable quantisation, then measure actual latency and memory use. Quantisation stores weights with fewer bits, reducing RAM and often improving CPU practicality at some potential quality cost. Treat embedding and reranking models as separate, task-specific choices.

Keep model artefacts separate from application code and never hard-code a model or Ollama URL into applications. Use a provider/model configuration layer so an application can move between Ollama, another local runtime, self-hosted cloud inference, and commercial APIs.
