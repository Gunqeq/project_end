document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");

    function addMessage(text, type) {
        const div = document.createElement("div");
        div.className = type === "user" ? "user-msg" : "bot-msg";
        div.textContent = text;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const text = input.value.trim();
        if (!text) return;

        addMessage(text, "user");
        input.value = "";

        // typing indicator
        const typing = document.createElement("div");
        typing.className = "bot-msg";
        typing.textContent = "กำลังพิมพ์...";
        chatBox.appendChild(typing);

        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        });

        const data = await res.json();

        typing.remove();
        addMessage(data.response, "bot");
    });
});
