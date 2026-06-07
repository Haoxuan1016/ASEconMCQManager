(function () {
  const bank = window.QUESTION_BANK;
  const hardExplanations = window.HARD_EXPLANATIONS || { explanations: {} };
  const topicById = new Map(bank.topics.map((topic) => [topic.id, topic]));
  const state = {
    difficulty: "All",
    topic: "All",
    typeC: false,
    search: "",
    activeId: null,
  };

  const el = {
    summaryText: document.getElementById("summaryText"),
    difficultyButtons: document.getElementById("difficultyButtons"),
    runtimeNotice: document.getElementById("runtimeNotice"),
    topicSelect: document.getElementById("topicSelect"),
    typeCToggle: document.getElementById("typeCToggle"),
    paperSearch: document.getElementById("paperSearch"),
    questionList: document.getElementById("questionList"),
    resultCount: document.getElementById("resultCount"),
    pdfViewer: document.getElementById("pdfViewer"),
    explanationPanel: document.getElementById("explanationPanel"),
    activeTitle: document.getElementById("activeTitle"),
    activeMeta: document.getElementById("activeMeta"),
    openPdfLink: document.getElementById("openPdfLink"),
  };

  function topicName(id) {
    return topicById.get(id)?.name || id;
  }

  function shortTopic(id) {
    return {
      "basic-economic-ideas": "Basic Ideas",
      "price-system": "Price System",
      "government-micro-intervention": "Gov Micro",
      "macroeconomy": "Macroeconomy",
      "government-macro-intervention": "Gov Macro",
      "international-economic-issues": "International",
    }[id] || id;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function pdfPath(question) {
    return question.file;
  }

  function pdfSrc(question, reloadKey) {
    const key = encodeURIComponent(reloadKey || question.id);
    return `${encodeURI(pdfPath(question))}?reload=${key}#page=${question.page}&zoom=page-width`;
  }

  function loadPdfFrame(src) {
    const freshFrame = el.pdfViewer.cloneNode(false);
    freshFrame.src = src;
    el.pdfViewer.replaceWith(freshFrame);
    el.pdfViewer = freshFrame;
  }

  function matchesSearch(question) {
    if (!state.search) {
      return true;
    }
    const haystack = `${question.paper} q${question.questionNumber} ${question.file}`.toLowerCase();
    return haystack.includes(state.search);
  }

  function filteredQuestions() {
    return bank.questions.filter((question) => {
      if (state.difficulty !== "All" && question.difficulty !== state.difficulty) {
        return false;
      }
      if (state.topic !== "All" && question.topic !== state.topic) {
        return false;
      }
      if (state.typeC && !question.typeC) {
        return false;
      }
      return matchesSearch(question);
    });
  }

  function setActive(question) {
    state.activeId = question.id;
    const nextSrc = pdfSrc(question, `${question.id}-${Date.now()}`);
    el.activeTitle.innerHTML = `
      <span class="active-question-number">#${escapeHtml(question.questionNumber)}</span>
      <span class="active-paper-name">${escapeHtml(question.paper)}</span>
    `;
    el.activeMeta.textContent = `${question.difficulty} | ${topicName(question.topic)} | PDF page ${question.page}`;
    el.openPdfLink.href = nextSrc;
    loadPdfFrame(nextSrc);
    renderExplanation(question);
    renderList();
  }

  function renderExplanation(question) {
    const explanation = hardExplanations.explanations[question.id];
    if (!explanation) {
      el.explanationPanel.classList.remove("visible");
      el.explanationPanel.innerHTML = "";
      return;
    }

    const choices = "ABCD".split("").map((label) => {
      const sentences = explanation.choices[label] || [];
      const correct = label === explanation.answer;
      return `
        <article class="choice-explanation${correct ? " correct" : ""}">
          <h3>${label}${correct ? " - correct" : ""}</h3>
          <p>${escapeHtml(sentences.join(" "))}</p>
        </article>
      `;
    }).join("");

    el.explanationPanel.innerHTML = `
      <div class="answer-line">
        <span class="answer-pill">${escapeHtml(explanation.answer)}</span>
        <span>Sample answer and explanation</span>
      </div>
      <p class="conclusion">${escapeHtml(explanation.conclusion)}</p>
      <div class="choice-grid">${choices}</div>
    `;
    el.explanationPanel.classList.add("visible");
  }

  function renderDifficultyButtons() {
    const allButton = [{ id: "All", name: "All", count: bank.questions.length }].concat(bank.difficulties);
    el.difficultyButtons.innerHTML = "";
    allButton.forEach((difficulty) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${difficulty.name} ${difficulty.count}`;
      button.className = state.difficulty === difficulty.id ? "active" : "";
      button.addEventListener("click", () => {
        state.difficulty = difficulty.id;
        render();
      });
      el.difficultyButtons.appendChild(button);
    });
  }

  function renderTopics() {
    const current = state.topic;
    el.topicSelect.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "All";
    allOption.textContent = `All topics (${bank.questions.length})`;
    el.topicSelect.appendChild(allOption);
    bank.topics.forEach((topic) => {
      const option = document.createElement("option");
      option.value = topic.id;
      option.textContent = `${topic.name} (${topic.count})`;
      el.topicSelect.appendChild(option);
    });
    el.topicSelect.value = current;
  }

  function badge(text, className) {
    return `<span class="badge ${className || ""}">${text}</span>`;
  }

  function renderList() {
    const questions = filteredQuestions();
    el.resultCount.textContent = `${questions.length} match${questions.length === 1 ? "" : "es"}`;

    if (!questions.length) {
      el.questionList.innerHTML = '<div class="empty">No matching questions</div>';
      return;
    }

    el.questionList.innerHTML = questions.map((question) => {
      const active = question.id === state.activeId ? " active" : "";
      const cues = question.cues.length ? question.cues.join(", ") : "classified by topic keywords";
      return `
        <button class="question-item${active}" type="button" data-id="${question.id}">
          <span class="item-title">
            <span>${question.paper}</span>
            <span>Q${question.questionNumber}</span>
          </span>
          <span class="item-meta">Page ${question.page} | ${shortTopic(question.topic)}</span>
          <span class="badges">
            ${badge(question.difficulty, question.difficulty.toLowerCase())}
            ${question.typeC ? badge("Type C", "type-c") : ""}
          </span>
          <span class="item-cues">${cues}</span>
        </button>
      `;
    }).join("");

    el.questionList.querySelectorAll(".question-item").forEach((button) => {
      button.addEventListener("click", () => {
        const question = bank.questions.find((item) => item.id === button.dataset.id);
        if (question) {
          setActive(question);
        }
      });
    });
  }

  function ensureActive() {
    const questions = filteredQuestions();
    if (!questions.length) {
      return;
    }
    const activeStillVisible = questions.some((question) => question.id === state.activeId);
    if (!activeStillVisible) {
      setActive(questions[0]);
    }
  }

  function render() {
    renderDifficultyButtons();
    renderTopics();
    ensureActive();
    renderList();
  }

  function init() {
    if (window.location.protocol === "file:") {
      document.body.classList.add("has-runtime-notice");
      el.runtimeNotice.hidden = false;
      el.runtimeNotice.textContent = "Open this page through http://127.0.0.1:8765/index.html for reliable PDF display; browser PDF viewers can block file:// frames.";
    }
    el.summaryText.textContent = `${bank.summary.questionCount} questions | ${bank.summary.paperCount} papers | ${bank.summary.typeCCount} Type C`;
    el.topicSelect.addEventListener("change", () => {
      state.topic = el.topicSelect.value;
      render();
    });
    el.typeCToggle.addEventListener("change", () => {
      state.typeC = el.typeCToggle.checked;
      render();
    });
    el.paperSearch.addEventListener("input", () => {
      state.search = el.paperSearch.value.trim().toLowerCase();
      render();
    });
    state.activeId = bank.questions[0]?.id || null;
    if (bank.questions[0]) {
      setActive(bank.questions[0]);
    }
    render();
  }

  init();
})();
