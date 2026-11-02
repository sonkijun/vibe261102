// 진입점: 사용자 이벤트를 store 호출로 연결하고, 상태가 바뀌면 다시 그린다.
(function () {
  const store = TodoStore;
  const ui = TodoRender;

  const form = document.getElementById('todo-form');
  const input = document.getElementById('new-todo');
  const list = document.getElementById('todo-list');

  let editingId = null;
  let pendingFocus = null;

  function draw() {
    ui.render({
      dateLabel: TodoDate.formatLong(),
      todos: store.getTodos(),
      stats: store.getStats(),
      editingId,
      storageOk: store.isStorageOk(),
      focusKey: pendingFocus,
    });
    pendingFocus = null;
  }

  function idOf(element) {
    return element.closest('.todo-item')?.dataset.id ?? null;
  }

  // ---------- 추가 ----------
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const todo = store.addTodo(input.value);
    if (!todo) {
      input.classList.remove('shake');
      void input.offsetWidth; // 애니메이션 재시작
      input.classList.add('shake');
      input.focus();
      return;
    }
    input.value = '';
    input.focus();
  });

  input.addEventListener('animationend', () => input.classList.remove('shake'));
  input.addEventListener('input', () => input.classList.remove('shake'));

  // ---------- 삭제 ----------
  function removeTodo(id) {
    const snapshot = store.deleteTodo(id);
    if (!snapshot) return;
    ui.showToast('할 일을 삭제했어요', () => store.restoreTodo(snapshot));
    input.focus();
  }

  // ---------- 수정 ----------
  function startEdit(id) {
    if (!store.getTodo(id)) return;
    editingId = id;
    draw();
  }

  /** @param {HTMLInputElement} field  @param {boolean} keepFocus Enter로 끝냈을 때 수정 버튼으로 포커스 복귀 */
  function commitEdit(field, keepFocus) {
    const id = idOf(field);
    // 다시 그리는 과정에서 focusout이 한 번 더 들어와도 무시한다
    if (!id || editingId !== id) return;
    editingId = null;

    const text = field.value.trim();
    if (!text) {
      if (window.confirm('내용이 비어 있어요. 이 할 일을 삭제할까요?')) {
        removeTodo(id);
      } else {
        if (keepFocus) pendingFocus = `edit:${id}`;
        draw();
      }
      return;
    }

    if (keepFocus) pendingFocus = `edit:${id}`;
    const todo = store.getTodo(id);
    if (todo && todo.text === text) {
      draw(); // 변경 없음: 편집 모드만 닫는다
    } else {
      store.updateTodo(id, text); // 구독자가 다시 그린다
    }
  }

  function cancelEdit(field) {
    const id = idOf(field);
    if (!id || editingId !== id) return;
    editingId = null;
    pendingFocus = `edit:${id}`;
    draw();
  }

  // ---------- 목록 이벤트 위임 ----------
  list.addEventListener('change', (event) => {
    if (event.target.matches('.todo-toggle')) {
      store.toggleTodo(idOf(event.target));
    }
  });

  list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const id = idOf(button);
    if (button.dataset.action === 'edit') startEdit(id);
    if (button.dataset.action === 'delete') removeTodo(id);
  });

  list.addEventListener('dblclick', (event) => {
    if (event.target.matches('.todo-text')) startEdit(idOf(event.target));
  });

  list.addEventListener('keydown', (event) => {
    if (!event.target.matches('.todo-edit') || event.isComposing) return;
    if (event.key === 'Enter') {
      event.preventDefault();
      commitEdit(event.target, true);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      cancelEdit(event.target);
    }
  });

  list.addEventListener('focusout', (event) => {
    if (event.target.matches('.todo-edit')) commitEdit(event.target, false);
  });

  // ---------- 날짜 변경 감지 (자정을 넘겨 페이지를 열어둔 경우) ----------
  function checkDate() {
    if (store.syncDate()) {
      editingId = null;
      ui.hideToast();
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') checkDate();
  });
  window.addEventListener('focus', checkDate);
  form.addEventListener('pointerdown', checkDate, true);
  list.addEventListener('pointerdown', checkDate, true);
  setInterval(checkDate, 60 * 1000);

  store.subscribe(draw);
  draw();
})();
