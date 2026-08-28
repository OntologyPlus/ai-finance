const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export interface OntologyMeta {
  scene_id: string;
  scene_name: string;
  stage?: string;
  confidence: number;
  matched_objects?: string[];
  activated_rules?: string[];
  activated_behaviors?: string[];
  agent_name?: string;
  elapsed_ms?: number;
}

export interface SSEHandlers {
  onThinking: (data: { session_id: string; message: string }) => void;
  onIntent: (data: { intent: string; confidence: number; scene_id?: string }) => void;
  onRouting: (data: { agent: string; intent: string; confidence: number }) => void;
  onOntology: (data: OntologyMeta) => void;
  onContent: (data: { chunk: string; session_id: string }) => void;
  onToolsUsed: (data: { tools: string[] }) => void;
  onSuggestions: (data: { suggestions: string[] }) => void;
  onDone: (data: { session_id: string; intent: string; agent: string }) => void;
  onError: (data: { message: string; session_id?: string }) => void;
}

export async function sendChatMessage(
  message: string,
  handlers: SSEHandlers,
  signal?: AbortSignal,
  sessionId?: string,
  pageContext?: Record<string, string>
): Promise<void> {
  try {
    const response = await fetch(`${BASE_URL}/api/stream/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: message }],
        context: pageContext || {},
        stream: true,
        session_id: sessionId,
      }),
      signal,
    });

    if (!response.ok) {
      handlers.onError({ message: `HTTP ${response.status}: ${response.statusText}` });
      return;
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith('data: ') && currentEvent) {
          const rawData = line.slice(6);
          try {
            const parsed = JSON.parse(rawData);
            const data = parsed.data !== undefined ? parsed.data : parsed;

            switch (currentEvent) {
              case 'thinking':
                handlers.onThinking(data);
                break;
              case 'intent':
                handlers.onIntent(data);
                break;
              case 'routing':
                handlers.onRouting(data);
                break;
              case 'ontology':
                handlers.onOntology(data);
                break;
              case 'content':
                handlers.onContent(data);
                break;
              case 'tools_used':
                handlers.onToolsUsed(data);
                break;
              case 'suggestions':
                handlers.onSuggestions(data);
                break;
              case 'done':
                handlers.onDone(data);
                break;
              case 'error':
                handlers.onError(data);
                break;
            }
          } catch {
            // ignore parse errors
          }
          currentEvent = '';
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      return;
    }
    handlers.onError({ message: err instanceof Error ? err.message : 'Unknown error' });
  }
}
