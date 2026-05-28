const input = document.getElementById("commandInput");
const sendBtn = document.getElementById("sendBtn");
const log = document.getElementById("log");
const useScreenshot = document.getElementById("useScreenshot");
const autoAi = document.getElementById("autoAi");
const voiceBtn = document.getElementById("voiceBtn");

function addMessage(text, type = "") {
  const div = document.createElement("div");
  div.className = `message ${type}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function addActionBox(parent, action) {
  const box = document.createElement("div");
  box.className = "action-box";
  box.textContent = JSON.stringify(action, null, 2);
  parent.appendChild(box);
}

async function executeAction(action) {
  const res = await fetch("/api/execute", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(action)
  });

  const data = await res.json();

  if (data.ok) {
    addMessage("Действие выполнено.", "ok");
  } else {
    addMessage("Ошибка выполнения: " + data.message, "error");
  }
}

async function sendCommand() {
  const command = input.value.trim();
  if (!command) return;

  input.value = "";

  addMessage("> " + command, "user");

  sendBtn.disabled = true;
  sendBtn.textContent = "Думаю...";

  try {
    const res = await fetch("/api/command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        command,
        use_screenshot: useScreenshot.checked,
        auto_execute_ai: autoAi.checked
      })
    });

    const data = await res.json();

    const msg = addMessage(data.message || "Ответ получен.", data.ok ? "ok" : "error");

    if (data.action) {
      addActionBox(msg, data.action);
    }

    if (data.ok && data.type === "ai" && !data.executed) {
      const btn = document.createElement("button");
      btn.className = "confirm-btn";
      btn.textContent = "Выполнить действие";
      btn.onclick = () => {
        executeAction(data.action);
        btn.disabled = true;
        btn.textContent = "Выполнено";
      };
      msg.appendChild(btn);
    }
  } catch (err) {
    addMessage("Ошибка запроса: " + err.message, "error");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Выполнить";
    input.focus();
  }
}

sendBtn.addEventListener("click", sendCommand);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendCommand();
  }
});

async function listenVoice() {
  voiceBtn.disabled = true;
  voiceBtn.textContent = "Слушаю...";

  addMessage("Слушаю голосовую команду...", "user");

  try {
    const res = await fetch("/api/listen", {
      method: "POST"
    });

    const data = await res.json();

    if (!data.ok) {
      addMessage(data.message || "Не удалось распознать речь.", "error");
      return;
    }

    addMessage("Распознано: " + data.text, "ok");

    input.value = data.text;
    await sendCommand();

  } catch (err) {
    addMessage("Ошибка голосового ввода: " + err.message, "error");
  } finally {
    voiceBtn.disabled = false;
    voiceBtn.textContent = "Голос";
    input.focus();
  }
}

voiceBtn.addEventListener("click", listenVoice);

addMessage("Интерфейс запущен. Быстрые команды выполняются автономно.", "ok");