import { useEffect, useMemo, useRef, useState } from "react";
import {
  chatWithDocument,
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

function App() {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  const [strategy, setStrategy] = useState("auto");
  const [provider, setProvider] = useState("compatible");
  
  const [rerank, setRerank] = useState(true);
  const [rerankCandidateLimit, setRerankCandidateLimit] = useState(12);

  type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
};

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
    const frame = window.requestAnimationFrame(() => {
      chatEndRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [messages.length, loadingMode]);

  const bestStrategy = useMemo(() => {
  if (!evaluation?.strategy_results?.length) return null;

  return [...evaluation.strategy_results].sort(
    (a, b) => b.overall_score - a.overall_score
  )[0];
}, [evaluation]);

 const selectedDocument = useMemo(() => {
  if (!selectedDocumentId) return null;

  return (
    documents.find((document) => document.document_id === selectedDocumentId) ??
    null
  );
}, [documents, selectedDocumentId]);

const documentProfile = selectedDocument?.document_profile ?? null;

const selectedStrategyLabel =
  strategy === "auto" && documentProfile
    ? `auto → ${documentProfile.recommended_strategy}`
    : strategy;

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;

    setError("");
    setLoadingMode("upload");

    try {
      const result = await uploadDocuments(files);
      setDocuments(result.documents);
      setMessages([]);
      setChatResponse(null);
      setEvaluation(null);
      if (result.documents.length > 0) {
        setSelectedDocumentId(result.documents[0].document_id);
        setStrategy("auto");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoadingMode("");
    }
  }

  async function handleChat() {
  const trimmedQuestion = question.trim();

  if (!trimmedQuestion || !selectedDocumentId) return;

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
      limit: documentProfile?.recommended_top_k ?? 3,
      rerank,
      rerankCandidateLimit,
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
              onChange={(event) => {
                setSelectedDocumentId(event.target.value);
                setStrategy("auto");
                setEvaluation(null);
                setChatResponse(null);
                setMessages([]);
              }}
            >
              <option value="">All indexed documents</option>
              {documents.map((document) => (
                <option key={document.document_id} value={document.document_id}>
                  {document.original_filename}
                </option>
              ))}
            </select>
          </div>

          {documentProfile && (
            <div className="strategy-summary">
              <p>Document processed successfully</p>

              <strong>
                {documentProfile.recommended_strategy}, top_k=
                {documentProfile.recommended_top_k}
              </strong>

              <span>
                Detected {documentProfile.page_count} pages ·{" "}
                {documentProfile.detected_structure.replaceAll("_", " ")} ·{" "}
                {documentProfile.table_count > 0
                  ? `${documentProfile.table_count} table blocks`
                  : "low table density"}
              </span>

              <div className="strategy-explanation">
                <p>
                  <strong>Reason:</strong> {documentProfile.reason}
                </p>
                <p>
                  <strong>Structure:</strong> {documentProfile.heading_count} headings ·{" "}
                  {documentProfile.avg_page_chars} avg page chars
                </p>
              </div>
            </div>
          )}

          <div className="step-group">
            <label className="step-label">
              Chunking strategy <span>retrieval</span>
            </label>
            <select
              value={strategy}
              onChange={(event) => setStrategy(event.target.value)}
            >
              <option value="auto">
                Auto recommended
                {documentProfile
                  ? ` (${documentProfile.recommended_strategy}, top_k=${documentProfile.recommended_top_k})`
                  : ""}
              </option>

              {STRATEGIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>





          <div className="step-group">
            <label className="step-label">
              Reranking <span>second stage</span>
            </label>

            <label className="toggle-row">
              <input
                type="checkbox"
                checked={rerank}
                onChange={(event) => setRerank(event.target.checked)}
              />
              <span>
                Retrieve more candidate chunks, rerank them, then send only the best chunks
                to the LLM.
              </span>
            </label>

            <select
              value={rerankCandidateLimit}
              onChange={(event) => setRerankCandidateLimit(Number(event.target.value))}
              disabled={!rerank}
            >
              <option value={8}>Candidate pool: 8</option>
              <option value={12}>Candidate pool: 12</option>
              <option value={20}>Candidate pool: 20</option>
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
              disabled={loadingMode !== "" || !selectedDocumentId}
            >
            {loadingMode === "evaluation"
            ? "Running retrieval evaluation..."
            : "Run retrieval evaluation"}
          </button>

          {bestStrategy && (
            <div className="best-box">
              <p>Quick retrieval winner</p>
              <strong>{bestStrategy.strategy}</strong>
              <span>
                Avg recall {bestStrategy.average_keyword_recall} · Pass rate{" "}
                {bestStrategy.pass_rate}
              </span>
            </div>
          )}
        </aside>

        <section className="panel chat-panel">
          <div className="chat-header">
            <div>
              <h2>Document chat TEST BUBBLES</h2>
              <p>Answers are generated only from retrieved document chunks.</p>
            </div>
            <span className="status-pill">{selectedStrategyLabel}</span>
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
        Upload a document, use the recommended retrieval policy, and ask a question.
        The assistant will answer with grounded evidence from retrieved chunks.
      </p>
    </div>
  </div>
)}

{messages.map((message) => (
  <article
    key={message.id}
    className={`message-row ${
      message.role === "user" ? "message-row-user" : "message-row-assistant"
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
              {message.response.used_strategy ?? message.response.strategy} · top_k{" "}
              {message.response.used_top_k ?? "—"} · rerank{" "}
              {message.response.used_reranking ? "on" : "off"} · candidates{" "}
              {message.response.rerank_candidate_limit ?? "—"} · provider{" "}
              
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
        <div ref={chatEndRef} className="chat-scroll-anchor" />

            
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
              disabled={loadingMode !== "" || !selectedDocumentId}
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
                    Source {index + 1} ·{" "}
                    {source.page_number ? `p.${source.page_number}` : "page unknown"} ·{" "}
                    {source.section_title || "Unknown section"} · similarity{" "}
                    {(source.similarity_score ?? source.score).toFixed(3)}
                    {source.rerank_score !== null && source.rerank_score !== undefined
                      ? ` · reranked #${index + 1}`
                      : ""}
                  </summary>

                  <div className="source-meta">
                    <span>{source.document_name}</span>
                    <span>{source.strategy}</span>
                    <span>{source.chunk_type}</span>
                    <span>chunk {source.chunk_index}</span>

                    {source.original_rank !== null && source.original_rank !== undefined && (
                      <span>original rank {source.original_rank}</span>
                    )}

                    {source.rerank_score !== null && source.rerank_score !== undefined && (
                      <span>rerank score {source.rerank_score.toFixed(3)} higher is better</span>
                    )}

                    {source.original_rank !== null && source.original_rank !== undefined && (
                      <span>original rank {source.original_rank}</span>
                    )}
                  </div>

                  <p>{source.text}</p>
                </details>
              ))}
            </div>
          )}

          {evaluation && (
            <>
              <div className="evaluation-table-wrap">
                <table className="evaluation-table">
                  <thead>
                    <tr>
                      <th>Strategy</th>
                      <th>Questions</th>
                      <th>Recall</th>
                      <th>Pass rate</th>
                      <th>Avg similarity</th>
                      <th>Overall</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.strategy_results.map((result) => (
                      <tr key={result.strategy}>
                        <td>{result.strategy}</td>
                        <td>{result.questions_evaluated}</td>
                        <td>{result.average_keyword_recall.toFixed(2)}</td>
                        <td>{result.pass_rate.toFixed(2)}</td>
                        <td>
                          {result.average_top_score !== null &&
                          result.average_top_score !== undefined
                            ? result.average_top_score.toFixed(3)
                            : "—"}
                        </td>
                        <td>{result.overall_score.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
                {evaluation.best_strategy && (
                  <div className="strategy-summary">
                    <p>Quick retrieval result</p>
                    <strong>{evaluation.best_strategy}</strong>
                    <span>{evaluation.best_strategy_reason}</span>
                  </div>
                )}
              {evaluation.strategy_results.map((strategyResult) => (
                <details key={strategyResult.strategy} className="eval-details">
                  <summary>{strategyResult.strategy} question details</summary>
                  <div className="strategy-explanation">
                    <p>
                        <strong>Recommendation:</strong> {strategyResult.recommendation}
                    </p>
                    <p>
                        <strong>Strengths:</strong> {strategyResult.strengths.join(" ")}
                    </p>
                    <p>
                        <strong>Weaknesses:</strong> {strategyResult.weaknesses.join(" ")}
                    </p>
                    </div>
                  {strategyResult.results.map((result) => (
                    <div key={result.question_id} className="eval-card">
                      <div className="eval-card-header">
                        <strong>
                          {result.question_id}: {result.question}
                        </strong>

                        <span className={result.passed ? "pass-pill" : "fail-pill"}>
                          {result.passed ? "Passed" : "Failed"}
                        </span>
                      </div>

                      <div className="question-metrics">
                        <span>Recall {result.keyword_recall.toFixed(2)}</span>
                        <span>
                          Top similarity{" "}
                          {result.top_score !== null && result.top_score !== undefined
                            ? result.top_score.toFixed(3)
                            : "—"}
                        </span>
                      </div>

                      <p>
                        <strong>Matched:</strong>{" "}
                        {result.matched_keywords.length
                          ? result.matched_keywords.join(", ")
                          : "None"}
                      </p>

                      <p>
                        <strong>Missing:</strong>{" "}
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