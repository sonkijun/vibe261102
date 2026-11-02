// DOM 렌더링: 전달받은 상태만 보고 화면을 그린다. 사용자 입력은 항상 textContent로 넣는다(XSS 방지).
(function () {
  const $ = (id) => document.getElementById(id);

  const els = {
    banner: $('storage-banner'),
    date: $('today-date'),
    progress: $('progress'),
    progressTrack: $('progress-track'),
    progressBar: $('progress-bar'),
    progressText: $('progress-text'),
    celebrate: $('celebrate'),
    list: $('todo-list'),
    empty: $('empty-state'),
    footer: $('footer'),
    remaining: $('remaining-count'),
    toast: $('toast'),
    toastMessage: $('toast-message'),
    toastUndo: $('toast-undo'),
  };

  const ICONS = {
    edit:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    delete:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  };

  function iconButton(action, todo, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `icon-button ${action}`;
    button.dataset.action = action;
    button.dataset.focusKey = `${action}:${todo.id}`;
    button.setAttribute('aria-label', `${label}: ${todo.text}`);
    button.innerHTML = ICONS[action]; // 고정된 아이콘 마크업만 사용
    return button;
  }

  // 직전 렌더에 있던 항목 id. 새로 생긴 항목에만 등장 애니메이션을 준다 (첫 렌더는 제외)
  let renderedIds = null;

  function createItem(todo, isEditing) {
    const li = document.createElement('li');
    li.className = 'todo-item' + (todo.completed ? ' is-done' : '');
    if (renderedIds && !renderedIds.has(todo.id)) li.classList.add('is-new');
    li.dataset.id = todo.id;

    const hit = document.createElement('label');
    hit.className = 'toggle-hit';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'todo-toggle';
    checkbox.checked = todo.completed;
    checkbox.dataset.focusKey = `toggle:${todo.id}`;
    checkbox.setAttribute('aria-label', `완료: ${todo.text}`);
    hit.append(checkbox);
    li.append(hit);

    if (isEditing) {
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'todo-edit';
      input.value = todo.text;
      input.maxLength = TodoStore.MAX_LENGTH;
      input.setAttribute('aria-label', '할 일 수정');
      input.enterKeyHint = 'done';
      li.append(input);
    } else {
      const text = document.createElement('span');
      text.className = 'todo-text';
      text.textContent = todo.text;
      text.title = '더블클릭해서 수정';
      li.append(text, iconButton('edit', todo, '수정'));
    }

    li.append(iconButton('delete', todo, '삭제'));
    return li;
  }

  function renderProgress(stats) {
    els.progress.hidden = stats.total === 0;
    els.progressBar.style.width = `${stats.percent}%`;
    els.progressText.textContent = `${stats.done} / ${stats.total} (${stats.percent}%)`;
    els.progressTrack.setAttribute('aria-valuenow', String(stats.percent));
    els.progressTrack.setAttribute('aria-valuetext', `${stats.total}개 중 ${stats.done}개 완료`);
    els.celebrate.hidden = !(stats.total > 0 && stats.done === stats.total);
  }

  /**
   * @param {{dateLabel: string, todos: object[], stats: object, editingId: string|null,
   *          storageOk: boolean, focusKey?: string|null}} state
   */
  function render(state) {
    // 목록을 다시 그려도 키보드 포커스가 같은 컨트롤에 남도록 기억해 둔다
    const focusKey = state.focusKey ?? document.activeElement?.dataset?.focusKey ?? null;

    els.banner.hidden = state.storageOk;
    els.date.textContent = state.dateLabel;
    renderProgress(state.stats);

    els.list.replaceChildren(
      ...state.todos.map((todo) => createItem(todo, todo.id === state.editingId))
    );
    renderedIds = new Set(state.todos.map((todo) => todo.id));
    els.empty.hidden = state.todos.length > 0;
    els.footer.hidden = state.stats.total === 0;
    els.remaining.textContent =
      state.stats.remaining === 0 ? '모두 완료' : `${state.stats.remaining}개 남음`;

    const editInput = els.list.querySelector('.todo-edit');
    if (editInput) {
      editInput.focus();
      editInput.setSelectionRange(editInput.value.length, editInput.value.length);
    } else if (focusKey) {
      els.list.querySelector(`[data-focus-key="${CSS.escape(focusKey)}"]`)?.focus();
    }
  }

  // ---------- 토스트 ----------
  let toastTimer = null;
  let toastUndo = null;

  function hideToast() {
    clearTimeout(toastTimer);
    toastTimer = null;
    toastUndo = null;
    els.toast.hidden = true;
  }

  function showToast(message, onUndo, duration = 5000) {
    clearTimeout(toastTimer);
    els.toastMessage.textContent = message;
    toastUndo = onUndo;
    els.toast.hidden = false;
    toastTimer = setTimeout(hideToast, duration);
  }

  els.toastUndo.addEventListener('click', () => {
    const undo = toastUndo;
    hideToast();
    if (undo) undo();
  });

  window.TodoRender = { render, showToast, hideToast };
})();
