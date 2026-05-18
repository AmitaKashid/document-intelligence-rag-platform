import { useMemo, useState } from "react";
import {
  ChatResponse,
  EvaluationResponse,
  UploadedDocument,
  chatWithDocument,
  runEvaluation,
  uploadDocuments,
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
  const [strategy, setStrategy] = useState("section_aware");
  const [provider, setProvider] = useState("compatible");
  const [question, setQuestion] = useState("");
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  const bestStrategy = useMemo(() => {
    if (!evaluation?.strategy_results?.length) return null;

    return [...evaluation.strategy_results].sort(
      (a, b) => b.average_keyword_recall - a.average_keyword_recall
    )[0];
  }, [evaluation]);

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;

    setError("");
    setLoading("Uploading and indexing documents...");

    try {
      const result = await uploadDocuments(files);
      setDocuments(result.documents);

      if (result.documents.length > 0) {
        setSelectedDocumentId(result.documents[0].document_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading("");
    }
  }

  async function handleChat() {
    if (!question.trim()) return;

    setError("");
    setLoading("Generating grounded answer...");

    try {
      const result = await chatWithDocument({
        question,
        documentId: selectedDocumentId,
        strategy,
        provider,
        limit: 5,
      });

      setChatResponse(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed.");
    } finally {
      setLoading("");
    }
  }

  async function handleEvaluation() {
    setError("");
    setLoading("Running retrieval evaluation...");

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
      setLoading("");
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Document Intelligence RAG Platform</p>
          <h1>Upload PDFs, compare retrieval strategies, and chat with sources.</h1>
          <p className="subtitle">
            Built with Docling parsing, multi-strategy chunking, BGE-M3 embeddings,
            Qdrant retrieval, Groq-compatible generation, and retrieval evaluation.
          </p>
        </div>
      </section>

      <section className="layout">
        <aside className="panel">
          <h2>1. Upload PDFs</h2>
          <input
            type="file"
            accept="application/pdf"
            multiple
            onChange={(event) => handleUpload(event.target.files)}
          />

          <h2>2. Select document</h2>
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

          <h2>3. Retrieval strategy</h2>
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

          <h2>4. Answer provider</h2>
          <select
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
          >
            <option value="compatible">Groq / OpenAI-compatible</option>
            <option value="extractive">Extractive fallback</option>
          </select>

          <button onClick={handleEvaluation}>Run evaluation</button>

          {bestStrategy && (
            <div className="best-box">
              <p>Best current strategy</p>
              <strong>{bestStrategy.strategy}</strong>
              <span>
                Avg recall: {bestStrategy.average_keyword_recall} | Pass rate:{" "}
                {bestStrategy.pass_rate}
              </span>
            </div>
          )}
        </aside>

        <section className="main-panel">
          <div className="chat-box">
            <h2>Chat</h2>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask something about the uploaded document..."
            />
            <button onClick={handleChat}>Ask document</button>

            {loading && <p className="status">{loading}</p>}
            {error && <pre className="error">{error}</pre>}

            {chatResponse && (
              <article className="answer-card">
                <h3>Answer</h3>
                <p>{chatResponse.answer}</p>

                <h3>Sources</h3>
                <div className="sources">
                  {chatResponse.sources.map((source, index) => (
                    <details key={source.chunk_id} className="source-card">
                      <summary>
                        Source {index + 1}: {source.document_name} |{" "}
                        {source.section_title || "Unknown section"} | score{" "}
                        {source.score.toFixed(3)}
                      </summary>
                      <p>{source.text}</p>
                    </details>
                  ))}
                </div>
              </article>
            )}
          </div>

          {evaluation && (
            <section className="evaluation">
              <h2>Retrieval evaluation</h2>
              <table>
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Questions</th>
                    <th>Average keyword recall</th>
                    <th>Pass rate</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluation.strategy_results.map((result) => (
                    <tr key={result.strategy}>
                      <td>{result.strategy}</td>
                      <td>{result.questions_evaluated}</td>
                      <td>{result.average_keyword_recall}</td>
                      <td>{result.pass_rate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="question-results">
                {evaluation.strategy_results.map((strategyResult) => (
                  <details key={strategyResult.strategy}>
                    <summary>{strategyResult.strategy} question-level results</summary>
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
              </div>
            </section>
          )}
        </section>
      </section>
    </main>
  );
}

export default App;