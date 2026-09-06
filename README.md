<h1>Accounts Payable Rule Extraction Engine</h1>

<h2>1. Overview</h2>
<p>This project is an automated Accounts Payable (AP) policy extraction engine designed to convert unstructured, natural language policy documents into deterministic, machine-executable JSON rules. It acts as a bridge between compliance documentation and automated execution systems by digesting narrative text, establishing a canonical data dictionary, and outputting strict logical rules complete with confidence scores, cross-reference validation, and end-to-end traceability.</p>

<h2>2. Problem Statement</h2>
<p><strong>Policy Document to Deterministic Rule Conversion</strong><br>
Modern AP systems rely on rigid rule engines, but the policies governing them are written in fluid, often ambiguous natural language. The challenge is to build a system that can accurately read a policy document, identify actionable constraints (approvals, tolerances, tax compliance), and transform them into a strictly typed, deterministic format that a machine can execute, all while maintaining traceability back to the source text and flagging logical contradictions.</p>

<h2>3. Solution Architecture</h2>
<p>The system operates as a 6-stage sequential pipeline designed to minimize errors and catch hallucinations via strict validation:</p>
<ol>
  <li><strong>Parser:</strong> Utilizes a hybrid regex and LLM approach to segment unstructured Markdown/TXT files into logical clauses. This isolates distinct rules and assigns them unique address references (e.g., Section 1.2).</li>
  <li><strong>Glossary Builder:</strong> Scans the isolated clauses to automatically extract a canonical list of variables (e.g., <code>grand_total_amount</code>, <code>po_number</code>). This establishes the ontology the rules must adhere to.</li>
  <li><strong>Extractor (3-Phase):</strong> The core engine. It translates English into natural pseudo-code first, forcing the LLM to make its logic explicit. It then extracts a document-specific action vocabulary, and finally converts the pseudo-code into strictly typed JSON mapped to our predefined schemas.</li>
  <li><strong>Structurer:</strong> Normalizes the extracted rules, assigning them sequential deterministic IDs (e.g., AP-001) and packaging them into a final <code>RuleSet</code> schema.</li>
  <li><strong>Validator:</strong> Acts as a logic safety net. It detects identical conditions triggering different actions, verifies all source clauses exist, and flags invented variables (fields not present in the glossary).</li>
  <li><strong>Main Orchestrator:</strong> Wires Stages 1 through 5 together into a single, automated end-to-end execution script.</li>
</ol>

<h2>4. Key Design Decisions</h2>
<table>
  <thead>
    <tr>
      <th>Decision</th>
      <th>Rationale</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Intermediate Pseudo-code Step</strong></td>
      <td><strong>Critical Innovation:</strong> Asking an LLM to go straight from English to JSON can cause logic mapping errors. Forcing an intermediate pseudo-code step makes the LLM explicitly define its logical branching (IF/THEN) before JSON generation.</td>
    </tr>
    <tr>
      <td><strong>Schema-Constrained Extraction</strong></td>
      <td>Using Pydantic models ensures the output JSON strictly adheres to the required structure. The LLM can only fill values, not invent random keys or nested objects.</td>
    </tr>
    <tr>
      <td><strong>Dynamic Action Vocabulary</strong></td>
      <td>Instead of hardcoding actions (like <code>APPROVE</code> or <code>REJECT</code>), the system extracts the verbs used <em>in the specific document</em>, allowing the pipeline to adapt to unseen policy types.</td>
    </tr>
    <tr>
      <td><strong>SQL-Syntax for Calculations</strong></td>
      <td>Forces the LLM to write derivations as ANSI SQL (e.g., <code>ABS(a - b) / b</code>). This prevents the LLM from inventing arbitrary mathematical notations.</td>
    </tr>
  </tbody>
</table>

<h2>5. Key Features Implemented</h2>
<ul>
  <li>Unstructured text to machine-readable JSON extraction</li>
  <li>Deterministic rule structure separating static thresholds from dynamic field comparisons</li>
  <li>Complete traceability (source clause addresses and raw text embedded in every rule)</li>
  <li>Automated field glossary generation (29 canonical fields)</li>
  <li>Conflict detection (identical conditions with differing actions)</li>
  <li>SQL-compliant mathematical formula derivations</li>
  <li>Confidence scoring (0.0 to 1.0) for every extracted rule</li>
</ul>

<h2>6. Results</h2>
<p>The pipeline successfully processes the provided AP Policy Document with the following metrics:</p>
<ul>
  <li><strong>Input:</strong> 1 unstructured document containing 35 distinct clauses across 7 sections.</li>
  <li><strong>Output:</strong> 48 machine-executable JSON rules.</li>
  <li><strong>Validation:</strong> 6 logical conflicts/issues detected and correctly flagged for human review.</li>
  <li><strong>Accuracy:</strong> Manually verified a majority of extracted rules for logical accuracy; found and corrected several classes of errors during development (see Known Limitations).</li>
  <li><strong>Performance:</strong> End-to-end execution time of roughly 10–12 minutes (rate-limited for free-tier API stability).</li>
</ul>

<h2>7. Getting Started</h2>
<p><strong>Prerequisites:</strong></p>
<ul>
  <li>Python 3.10+</li>
  <li>Google Gemini API Key</li>
</ul>
<p><strong>Installation & Setup:</strong></p>
<ol>
  <li>Clone the repository:<br>
    <pre><code>git clone &lt;repository_url&gt;<br>cd &lt;repository_directory&gt;</code></pre>
  </li>
  <li>Install required dependencies:<br>
    <pre><code>pip install pydantic python-dotenv google-genai</code></pre>
  </li>
  <li>Set up your environment variables by creating a <code>.env</code> file in the root directory:<br>
    <pre><code>GEMINI_API_KEY=your_actual_api_key_here</code></pre>
  </li>
  <li>Run the pipeline:<br>
    <pre><code>python main.py</code></pre>
    <em>(When prompted, enter <code>sample.md</code> located in the <code>sample_docs/</code> folder).</em>
  </li>
</ol>

<h2>8. Project Structure</h2>
<ul>
  <li><strong>output/</strong> — Generated rules and validation issues
    <ul>
      <li><code>Sample_AP_Policy_Document_rules.json</code></li>
    </ul>
  </li>
  <li><strong>sample_docs/</strong> — Input policy documents
    <ul>
      <li><code>Sample_AP_Policy_Document.md</code></li>
    </ul>
  </li>
  <li><strong>action_extractor.py</strong> — Extracts dynamic action vocabulary</li>
  <li><strong>extractor.py</strong> — 3-phase rule extraction engine</li>
  <li><strong>glossary_builder.py</strong> — Ontology and variable generation</li>
  <li><strong>main.py</strong> — Pipeline orchestrator</li>
  <li><strong>parser.py</strong> — Document segmentation logic</li>
  <li><strong>schema.py</strong> — Pydantic data models (Rule, RuleSet)</li>
  <li><strong>structurer.py</strong> — ID assignment and formatting</li>
  <li><strong>validator.py</strong> — Conflict and integrity checking</li>
  <li><strong>README.md</strong> — Project documentation</li>
</ul>

<h2>9. Sample Input/Output</h2>
<p><strong>Source Clause 2.2.a:</strong></p>
<blockquote>
  <p>"If the Invoice Total Amount is within +/- 1% of the PO Amount (tolerance), the invoice is auto-approved for booking."</p>
</blockquote>
<p><strong>Extracted JSON Rule (AP-006):</strong></p>
<pre><code>{
  "rule_id": "AP-006",
  "source_clauses": [
    "2.2.a"
  ],
  "description": "Auto-approve invoice for booking if the invoice total amount is within 1% of the PO amount.",
  "condition": {
    "operator": "AND",
    "conditions": [
      {
        "field": "invoice_total_amount",
        "derivation": "ABS(invoice_total_amount - po_amount) / po_amount",
        "op": "&lt;=",
        "value": 0.01,
        "compare_to_field": null
      }
    ]
  },
  "actions": [
    {
      "type": "AUTO_APPROVE",
      "target": null,
      "reason_code": null,
      "requires_justification": false
    }
  ],
  "confidence": 1.0,
  "raw_source_text": "If the Invoice Total Amount is within +/- 1% of the PO Amount (tolerance), the invoice is auto-approved for booking."
}</code></pre>

<h2>10. AI Tools Used</h2>
<ul>
  <li><strong>Model:</strong> Google Gemini 3.1 Flash (Free Tier via <code>google-genai</code> SDK).</li>
  <li><strong>Usage:</strong> Approximately 72 API calls per document.</li>
  <li><strong>Application:</strong> Used specifically for non-deterministic tasks: intelligently chunking messy document formatting, deducing canonical variable names, mapping natural language to pseudo-code, and structuring outputs. Python handles all routing, schema enforcement, and validation.</li>
</ul>

<h2>11. Known Limitations</h2>
<ul>
  <li><strong>Invented State Variables:</strong> In certain complex workflow clauses (e.g., "if not resolved within 48 hours"), the LLM may deduce a required system state (like <code>current_date</code> or <code>deviation_start_time</code>) that isn't explicitly defined in the text. The Validator successfully catches these as "Invented Fields", but it currently requires a human to officially add them to the system dictionary.</li>
  <li><strong>SQL Formula Edge Cases:</strong> While the system extracts math well, some complex derivations (e.g., self-referencing variable bugs or mismatched substring evaluations) can occasionally format poorly, requiring the validation stage to flag them.</li>
  <li><strong>PDF Currency Parsing:</strong> If feeding raw text extracted from a poorly formatted PDF, currency symbols (₹, $) occasionally cause the parser to misalign clause boundaries.</li>
  <li><strong>Field Reuse:</strong> The glossary builder sometimes extracts slightly different variations of the same concept (e.g., <code>vendor_gstin</code> vs <code>vendor_master_gstin</code>) depending on the prompt phrasing, requiring downstream validation checks.</li>
</ul>

<h2>12. Testing & Validation</h2>
<p>To test the pipeline, execute <code>main.py</code> and supply the sample document. To test on a new document, simply drop a raw <code>.txt</code> or <code>.md</code> file containing a company policy into the <code>sample_docs/</code> folder. The system is designed to generalize to new formats, though highly unstructured narrative text may result in lower confidence scores. Review the <code>"issues"</code> array at the bottom of the output JSON to see caught conflicts.</p>

<h2>13. Evaluation Criteria</h2>
<p><em>Self-assessment against the challenge's stated criteria:</em></p>
<table>
  <thead>
    <tr>
      <th>Criterion</th>
      <th>Self-Assessed Status</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Rule Traceability</strong></td>
      <td>Met</td>
      <td>Every rule contains an array of <code>source_clauses</code> and the <code>raw_source_text</code>.</td>
    </tr>
    <tr>
      <td><strong>Logic Accuracy</strong></td>
      <td>Met</td>
      <td>Manually verified for logical adherence; pseudo-code step prevents logic inversion.</td>
    </tr>
    <tr>
      <td><strong>Deterministic Output</strong></td>
      <td>Met</td>
      <td>Strict JSON schema utilizing enums for operators (<code>==</code>, <code>&gt;</code>, <code>&lt;=</code>).</td>
    </tr>
    <tr>
      <td><strong>Mathematical Handling</strong></td>
      <td>Met</td>
      <td>Expressed as SQL-style formulas for downstream parseability.</td>
    </tr>
    <tr>
      <td><strong>Conflict Detection</strong></td>
      <td>Met</td>
      <td>Stage 5 successfully identified 6 logic/field inconsistencies.</td>
    </tr>
  </tbody>
</table>

<h2>14. Future Enhancements / Bonus</h2>
<ul>
  <li><strong>Human-in-the-Loop (HITL) UI:</strong> A lightweight web dashboard to let a user review the Validator's flagged issues, map invented fields to canonical ones, and approve the final rule set.</li>
  <li><strong>Native Execution Export:</strong> An exporter module to convert the JSON output directly into execution scripts (like Python Pandas).</li>
  <li><strong>Advanced OCR Integration:</strong> Integrating a vision model to handle raw PDFs containing tables and flowcharts prior to Stage 1 parsing.</li>
</ul>

<h2>15. Appendix: Architecture Diagram</h2>
<pre><code>
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│ 1. Parser       ├────►│ 2. Glossary     ├────►│ 3. Extractor    │
│ (Regex + LLM)   │     │    Builder      │     │ (Pseudo-code)   │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│ Output Rules    │◄────┤ 5. Validator    │◄────┤ 4. Structurer   │
│ (.json)         │     │ (Conflict Check)│     │ (ID Assignment) │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
</code></pre>
