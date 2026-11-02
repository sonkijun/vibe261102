// 상태 관리 + localStorage 영속화. 상태가 단일 진실 공급원이며, 변경 시 구독자에게 알린다.
(function () {
  const STORAGE_KEY = 'todo:v1:days';
  const RETENTION_DAYS = 30;
  const MAX_LENGTH = 200;

  /** @type {Record<string, Array<object>>} 날짜 키별 할 일 목록 */
  let days = {};
  let currentKey = TodoDate.toKey();
  let storageOk = true;
  const listeners = new Set();

  function load() {
    let raw = null;
    try {
      raw = localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      storageOk = false;
      return;
    }

    try {
      const parsed = raw ? JSON.parse(raw) : {};
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        for (const [key, list] of Object.entries(parsed)) {
          if (Array.isArray(list)) days[key] = list;
        }
      }
    } catch (err) {
      console.warn('저장된 할 일 데이터를 읽지 못했습니다. 빈 목록으로 시작합니다.', err);
    }

    if (prune()) save();
  }

  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(days));
      storageOk = true;
    } catch (err) {
      storageOk = false;
    }
  }

  /** 보관 기간이 지났거나 키 형식이 잘못된 날짜를 지운다. 변경 여부를 반환 */
  function prune() {
    let changed = false;
    for (const key of Object.keys(days)) {
      const age = TodoDate.daysBetween(key, currentKey);
      const isEmptyPastDay = key !== currentKey && days[key].length === 0;
      if (Number.isNaN(age) || age > RETENTION_DAYS || isEmptyPastDay) {
        delete days[key];
        changed = true;
      }
    }
    return changed;
  }

  function commit() {
    save();
    listeners.forEach((fn) => fn());
  }

  function todayList() {
    if (!days[currentKey]) days[currentKey] = [];
    return days[currentKey];
  }

  function find(id) {
    return todayList().find((todo) => todo.id === id);
  }

  function normalize(text) {
    return String(text ?? '').trim().slice(0, MAX_LENGTH);
  }

  function createId() {
    if (window.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }

  // ---------- 공개 API ----------

  /** 할 일 추가. 빈 문자열이면 추가하지 않고 null 반환 */
  function addTodo(text) {
    const value = normalize(text);
    if (!value) return null;

    const list = todayList();
    const order = list.reduce((max, todo) => Math.max(max, todo.order), -1) + 1;
    const todo = {
      id: createId(),
      text: value,
      completed: false,
      priority: 'medium',
      order,
      createdAt: new Date().toISOString(),
      completedAt: null,
    };
    list.push(todo);
    commit();
    return todo;
  }

  function toggleTodo(id) {
    const todo = find(id);
    if (!todo) return;
    todo.completed = !todo.completed;
    todo.completedAt = todo.completed ? new Date().toISOString() : null;
    commit();
  }

  /** 텍스트 수정. 빈 문자열이면 수정하지 않고 false 반환 */
  function updateTodo(id, text) {
    const todo = find(id);
    const value = normalize(text);
    if (!todo || !value) return false;
    if (todo.text !== value) {
      todo.text = value;
      commit();
    }
    return true;
  }

  /** 삭제 후 복구용 스냅샷 반환 */
  function deleteTodo(id) {
    const list = todayList();
    const index = list.findIndex((todo) => todo.id === id);
    if (index === -1) return null;
    const [todo] = list.splice(index, 1);
    commit();
    return { dayKey: currentKey, todo };
  }

  /** 스냅샷을 원래 날짜에 되돌린다. order 값이 그대로라 원래 위치로 정렬된다 */
  function restoreTodo(snapshot) {
    if (!snapshot) return;
    const list = days[snapshot.dayKey] || (days[snapshot.dayKey] = []);
    if (list.some((todo) => todo.id === snapshot.todo.id)) return;
    list.push(snapshot.todo);
    commit();
  }

  function getTodos() {
    return todayList().slice().sort((a, b) => a.order - b.order);
  }

  function getTodo(id) {
    return find(id) || null;
  }

  function getStats() {
    const list = todayList();
    const total = list.length;
    const done = list.filter((todo) => todo.completed).length;
    return {
      total,
      done,
      remaining: total - done,
      percent: total === 0 ? 0 : Math.round((done / total) * 100),
    };
  }

  /** 자정이 지났으면 오늘 키를 바꾼다. 바뀌었으면 true */
  function syncDate() {
    const key = TodoDate.toKey();
    if (key === currentKey) return false;
    currentKey = key;
    prune();
    commit();
    return true;
  }

  function isStorageOk() {
    return storageOk;
  }

  function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  load();

  window.TodoStore = {
    MAX_LENGTH,
    addTodo,
    toggleTodo,
    updateTodo,
    deleteTodo,
    restoreTodo,
    getTodos,
    getTodo,
    getStats,
    syncDate,
    isStorageOk,
    subscribe,
  };
})();
