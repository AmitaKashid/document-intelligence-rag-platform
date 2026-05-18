import { useEffect, useMemo, useRef, useState } from "react";

import {
  chatWithDocument,
  listDocuments,
  runEvaluation,
  uploadDocuments,
} from "./api";

import type {
  ChatResponse,
  EvaluationResponse,
  UploadedDocument,
} from "./api";

import "./App.css";

const STRATEGIES = [
  "recursive",
  "section_aware",
  "table_preserving",
  "parent_child",
];

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
};

function App() {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");

  const [strategy, setStrategy] = useState(() => {
    return localStorage.getItem("rag_strategy") || "section_aware";
  });

  const [provider, setProvider] = useState(() => {
    return localStorage.getItem("rag_provider") || "compatible";
  });

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);

  const [loadingMode, setLoadingMode] = useState<
    "" | "upload" | "chat" | "evaluation"
  >("");

  const [error, setError] = useState("");

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, loadingMode]);

  useEffect(() => {
    localStorage.setItem("rag_strategy", strategy);
  }, [strategy]);

  useEffect(() => {
    localStorage.setItem("rag_provider", provider);
  }, [provider]);

  useEffect(() => {
    async function loadIndexedDocuments() {
      try {
        const result = await listDocuments();

        const loadedDocuments: UploadedDocument[] = result.documents.map(
          (document) => ({
            document_id: document.document_id,
            original_filename: document.document_name,
            status: "indexed",
          })
        );

        setDocuments(loadedDocuments);

        if (!selectedDocumentId && loadedDocuments.length > 0) {
          setSelectedDocumentId(loadedDocuments[0].document_id);
        }
      } catch (err) {
        console.warn("Could not load indexed documents", err);
      }
    }

    loadIndexedDocuments();
  }, []);

  const bestStrategy = useMemo(() => {
    if (!evaluation?.strategy_results?.length) return null;

    return [...evaluation.strategy_results].sort(
      (a, b) => b.overall_score - a.overall_score
    )[0];
  }, [evaluation]);

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;

    setError("");
    setLoadingMode("upload");

    try {
      const result = await uploadDocuments(files);

      setDocuments((current) => {
        const merged = [...current];

        for (const document of result.documents) {
          const exists = merged.some(
            (item) => item.document_id === document.document_id
          );

          if (!exists) {
            merged.push(document);
          }
        }

        return merged;
      });

      setMessages([]);
      setChatResponse(null);
      setEvaluation(null);

      if (result.documents.length > 0) {
        setSelectedDocumentId(result.documents[0].document_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoadingMode("");
    }
  }

  async function handleChat() {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) return;

    setError("");
    setLoadingMode("chat");

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");

    try {
      const result = await chatWithDocument({
        question: trimmedQuestion,
        documentId: selectedDocumentId,
        strategy,
        provider,
        limit: 5,
      });

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.answer,
        response: result,
      };

      setChatResponse(result);
      setMessages((current) => [...current, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed.");
    } finally {
      setLoadingMode("");
    }
  }

  async function handleEvaluation() {
    setError("");
    setLoadingMode("evaluation");

    try {
      const result = await runEvaluation({
        documentId: selectedDocumentId,
        strategies: STRATEGIES,
        limit: 5,
      });

      setEvaluation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation failed.");
    } finally {
      setLoadingMode("");
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <h1 className="brand-title">Document Intelligence RAG</h1>
            <p className="brand-subtitle">
              PDF chat, source-grounding, and retrieval strategy evaluation
            </p>
          </div>
        </div>

        <div className="topbar-status">
          <span className="status-pill">Docling</span>
          <span className="status-pill">BGE-M3</span>
          <span className="status-pill">Qdrant</span>
          <span className="status-pill">Groq</span>
        </div>
      </header>

      <section className="workspace">
        <aside className="panel control-panel">
          <div className="panel-heading">
            <div>
              <h2>Workspace controls</h2>
              <p>Upload PDFs, choose retrieval, then evaluate quality.</p>
            </div>
          </div>

          <div className="step-group">
            <label className="step-label">
              Upload PDFs <span>multiple</span>
            </label>
            <input
              type="file"
              accept="application/pdf"
              multiple
              onChange={(event) => handleUpload(event.target.files)}
            />
          </div>

          <div className="step-group">
            <label className="step-label">
              Document scope <span>{documents.length} loaded</span>
            </label>
            <select
              value={selectedDocumentId}
              onChange={(event) => setSelectedDocumentId(event.target.value)}
            >
              <option value="">All indexed documents</option>
              {documents.map((document) => (
                <option key={document.document_id} value={document.document_id}>
                  {document.original_filename}
                </option>
              ))}
            </select>
          </div>

          <div className="step-group">
            <label className="step-label">
              Chunking strategy <span>retrieval</span>
            </label>
            <select
              value={strategy}
              onChange={(event) => setStrategy(event.target.value)}
            >
              {STRATEGIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="step-group">
            <label className="step-label">
              Answer provider <span>generation</span>
            </label>
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              <option value="compatible">Groq / OpenAI-compatible</option>
              <option value="extractive">Extractive fallback</option>
            </select>
          </div>

          <button
            className="secondary-button"
            onClick={handleEvaluation}
            disabled={loadingMode !== ""}
          >
            {loadingMode === "evaluation"
              ? "Evaluating strategies..."
              : "Run strategy evaluation"}
          </button>

          {bestStrategy && (
            <div className="best-box">
              <p>Best current strategy</p>
              <strong>{bestStrategy.strategy}</strong>
              <span>
                Overall {bestStrategy.overall_score} · Avg recall{" "}
                {bestStrategy.average_keyword_recall} · Pass rate{" "}
                {bestStrategy.pass_rate}
              </span>
            </div>
          )}
        </aside>

        <section className="panel chat-panel">
          <div className="chat-header">
            <div>
              <h2>Document chat</h2>
              <p>Answers are generated only from retrieved document chunks.</p>
            </div>

            <div className="chat-actions">
              <button
                className="small-button"
                onClick={() => {
                  setMessages([]);
                  setChatResponse(null);
                  setError("");
                }}
                disabled={messages.length === 0 || loadingMode !== ""}
              >
                Clear chat
              </button>
              <span className="status-pill">{strategy}</span>
            </div>
          </div>

          <div className="chat-body">
            {loadingMode === "upload" && (
              <div className="status">
                Uploading, parsing, chunking, embedding, and indexing...
              </div>
            )}

            {loadingMode === "evaluation" && (
              <div className="status">
                Running retrieval evaluation across chunking strategies...
              </div>
            )}

            {error && <pre className="error">{error}</pre>}

            {messages.length === 0 && loadingMode === "" && (
              <div className="empty-state">
                <div>
                  <h3>Ask a question about your uploaded PDF</h3>
                  <p>
                    Upload a document, select a chunking strategy, and ask a
                    question. The assistant will answer with grounded evidence
                    from retrieved chunks.
                  </p>
                </div>
              </div>
            )}

            {messages.map((message) => (
              <article
                key={message.id}
                className={`message-row ${
                  message.role === "user"
                    ? "message-row-user"
                    : "message-row-assistant"
                }`}
              >
                <div
                  className={`message-bubble ${
                    message.role === "user" ? "user-bubble" : "assistant-bubble"
                  }`}
                >
                  <div className="message-meta">
                    {message.role === "user" ? "You" : "Assistant"}
                  </div>
                  <p>{message.content}</p>

                  {message.role === "assistant" && message.response && (
                    <div className="message-footnote">
                      {message.response.sources.length} sources · strategy{" "}
                      {message.response.strategy} · provider{" "}
                      {message.response.provider}
                    </div>
                  )}
                </div>
              </article>
            ))}

            {loadingMode === "chat" && (
              <article className="message-row message-row-assistant">
                <div className="message-bubble assistant-bubble typing-bubble">
                  <div className="message-meta">Assistant</div>
                  <p>Thinking with retrieved document context...</p>
                </div>
              </article>
            )}

            <div ref={chatEndRef} />
          </div>

          <div className="composer">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleChat();
                }
              }}
              placeholder="Ask about the uploaded document. Press Enter to send, Shift+Enter for a new line."
            />
            <button
              className="primary-button"
              onClick={handleChat}
              disabled={loadingMode !== ""}
            >
              {loadingMode === "chat" ? "Generating answer..." : "Ask document"}
            </button>
          </div>
        </section>

        <aside className="panel insight-panel">
          <div className="panel-heading">
            <div>
              <h2>Evidence & evaluation</h2>
              <p>Inspect retrieved sources and compare chunking strategies.</p>
            </div>
          </div>

          <div className="metric-grid">
            <div className="metric-card">
              <p>Sources</p>
              <strong>{chatResponse?.sources.length ?? 0}</strong>
            </div>

            <div className="metric-card">
              <p>Strategies</p>
              <strong>{evaluation?.strategy_results.length ?? 4}</strong>
            </div>
          </div>

          {chatResponse && (
            <div className="source-list">
              {chatResponse.sources.map((source, index) => (
                <details key={source.chunk_id} className="source-card">
                  <summary>
                    Source {index + 1} · {source.section_title || "Unknown"} ·{" "}
                    {source.score.toFixed(3)}
                  </summary>
                  <p>{source.text}</p>
                </details>
              ))}
            </div>
          )}

          {evaluation && (
            <>
              {evaluation.best_strategy && (
                <div className="strategy-summary">
                  <p>Recommended strategy</p>
                  <strong>{evaluation.best_strategy}</strong>
                  <span>{evaluation.best_strategy_reason}</span>
                </div>
              )}

              <div className="evaluation-table-wrap">
                <table className="evaluation-table">
                  <thead>
                    <tr>
                      <th>Strategy</th>
                      <th>Recall</th>
                      <th>Top score</th>
                      <th>Pass</th>
                      <th>Overall</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.strategy_results.map((result) => (
                      <tr key={result.strategy}>
                        <td>{result.strategy}</td>
                        <td>{result.average_keyword_recall}</td>
                        <td>{result.average_top_score ?? "—"}</td>
                        <td>{result.pass_rate}</td>
                        <td>{result.overall_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {evaluation.strategy_results.map((strategyResult) => (
                <details key={strategyResult.strategy} className="eval-details">
                  <summary>{strategyResult.strategy} question details</summary>

                  <div className="strategy-explanation">
                    <p>
                      <strong>Recommendation:</strong>{" "}
                      {strategyResult.recommendation}
                    </p>
                    <p>
                      <strong>Strengths:</strong>{" "}
                      {strategyResult.strengths.join(" ")}
                    </p>
                    <p>
                      <strong>Weaknesses:</strong>{" "}
                      {strategyResult.weaknesses.join(" ")}
                    </p>
                  </div>

                  {strategyResult.results.map((result) => (
                    <div key={result.question_id} className="eval-card">
                      <strong>
                        {result.question_id}: {result.question}
                      </strong>
                      <p>Recall: {result.keyword_recall}</p>
                      <p>Passed: {result.passed ? "Yes" : "No"}</p>
                      <p>
                        Matched:{" "}
                        {result.matched_keywords.length
                          ? result.matched_keywords.join(", ")
                          : "None"}
                      </p>
                      <p>
                        Missing:{" "}
                        {result.missing_keywords.length
                          ? result.missing_keywords.join(", ")
                          : "None"}
                      </p>
                    </div>
                  ))}
                </details>
              ))}
            </>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;
