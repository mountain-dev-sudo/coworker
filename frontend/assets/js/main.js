// COMPREHENSIVE FIX - Chat History Loading Issue
// Added extensive debugging and multiple fallback mechanisms

class CoworkerApp {
  constructor() {
    this.API_BASE_URL = "http://127.0.0.1:8000/api";
    this.currentChatId = null;
    this.chats = new Map();
    this.chatCounter = 1;
    this.isLoading = false;
    this.userMemory = {};
    this.isInitialized = false; // DEBUG: Track initialization

    this.init();
  }

  async init() {
    console.log("🚀 Initializing CoworkerApp..."); // DEBUG
    this.setupEventListeners();
    this.setupTheme();
    this.setupResponsive();
    this.setupTextareaAutoResize();

    // Load existing chats from backend or create new one
    await this.initializeApp();
  }

  setupEventListeners() {
    // Send message events
    document
      .getElementById("sendBtn")
      .addEventListener("click", () => this.sendMessage());
    document.getElementById("messageInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    document
      .getElementById("messageInput")
      .addEventListener("input", () => this.updateCharacterCount());

    // Chat management
    document
      .getElementById("newChatBtn")
      .addEventListener("click", () => this.createNewChat());

    // Theme toggle
    document
      .getElementById("themeToggle")
      .addEventListener("click", () => this.toggleTheme());

    // Clear all chats
    document
      .getElementById("clearAllBtn")
      .addEventListener("click", () => this.clearAllChats());

    // Mobile menu
    document
      .getElementById("mobileMenuBtn")
      .addEventListener("click", () => this.toggleSidebar());
    document
      .getElementById("sidebarOverlay")
      .addEventListener("click", () => this.closeSidebar());

    // Sidebar collapse (desktop)
    document
      .getElementById("collapseBtn")
      .addEventListener("click", () => this.toggleSidebar());
  }

  setupTheme() {
    const savedTheme = localStorage.getItem("coworker-theme") || "light";
    document.body.className = savedTheme + "-mode";
    this.updateThemeToggleText();
  }

  toggleTheme() {
    const isDark = document.body.classList.contains("dark-mode");
    document.body.className = isDark ? "light-mode" : "dark-mode";
    localStorage.setItem("coworker-theme", isDark ? "light" : "dark");
    this.updateThemeToggleText();
  }

  updateThemeToggleText() {
    const themeBtn = document.getElementById("themeToggle");
    const icon = themeBtn.querySelector("i");
    const text = themeBtn.querySelector(".btn-text");

    if (document.body.classList.contains("dark-mode")) {
      icon.className = "fas fa-sun";
      text.textContent = "Light Mode";
    } else {
      icon.className = "fas fa-moon";
      text.textContent = "Dark Mode";
    }
  }

  setupResponsive() {
    window.addEventListener("resize", () => {
      if (window.innerWidth > 768) {
        this.closeSidebar();
      }
    });
  }

  setupTextareaAutoResize() {
    const textarea = document.getElementById("messageInput");
    textarea.addEventListener("input", () => {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px";
    });
  }

  toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");

    sidebar.classList.toggle("open");
    overlay.classList.toggle("active");
  }

  closeSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");

    sidebar.classList.remove("open");
    overlay.classList.remove("active");
  }

  updateCharacterCount() {
    const input = document.getElementById("messageInput");
    const counter = document.getElementById("characterCount");
    const sendBtn = document.getElementById("sendBtn");

    const length = input.value.length;
    counter.textContent = `${length}/2000`;

    sendBtn.disabled = length === 0 || this.isLoading;

    if (length > 1800) {
      counter.style.color = "var(--danger-color)";
    } else if (length > 1500) {
      counter.style.color = "var(--text-secondary)";
    } else {
      counter.style.color = "var(--text-muted)";
    }
  }

  // FIXED: Initialize app with proper error handling and debugging
  async initializeApp() {
    console.log("📊 Starting app initialization..."); // DEBUG

    try {
      this.showAppLoading();

      // Step 1: Load user memory
      console.log("🧠 Loading user memory..."); // DEBUG
      await this.loadUserMemory();

      // Step 2: Try to load existing chats
      console.log("💬 Loading chats from backend..."); // DEBUG
      const chatsLoaded = await this.loadChatsFromBackend();

      console.log(
        `📋 Chats loaded: ${chatsLoaded}, Total chats: ${this.chats.size}`
      ); // DEBUG

      if (!chatsLoaded || this.chats.size === 0) {
        console.log("🆕 No chats found, creating new chat..."); // DEBUG
        await this.createNewChat();
      } else {
        // Step 3: Load the most recent chat's history
        const sortedChats = Array.from(this.chats.values()).sort(
          (a, b) => b.updatedAt - a.updatedAt
        );
        const mostRecentChat = sortedChats[0];

        console.log(`🎯 Most recent chat: ${mostRecentChat.id}`); // DEBUG

        this.currentChatId = mostRecentChat.id;

        // CRITICAL FIX: Load history immediately
        await this.loadChatHistory(this.currentChatId);

        // Force UI update
        this.forceUIUpdate();
      }

      this.isInitialized = true;
      console.log("✅ App initialization complete!"); // DEBUG
    } catch (error) {
      console.error("❌ Error initializing app:", error);
      this.showError("Failed to initialize app. Creating new chat...");

      // Fallback: create new chat
      await this.createNewChat();
      this.isInitialized = true;
    } finally {
      this.hideAppLoading();
    }
  }

  // FIXED: Robust method to load chats from backend
  async loadChatsFromBackend() {
    try {
      console.log("🔄 Fetching chats from API..."); // DEBUG

      const response = await fetch(`${this.API_BASE_URL}/chats`);

      if (!response.ok) {
        console.error(`❌ API response not OK: ${response.status}`);
        return false;
      }

      const data = await response.json();
      console.log("📦 Raw chats data:", data); // DEBUG

      if (data.chats && Array.isArray(data.chats)) {
        this.chats.clear();

        data.chats.forEach((chat, index) => {
          console.log(`📝 Processing chat ${index + 1}:`, chat); // DEBUG

          this.chats.set(chat.id, {
            id: chat.id,
            title: chat.title || "Untitled Chat",
            messages: [], // Will be loaded separately
            createdAt: new Date(chat.created_at || Date.now()),
            updatedAt: new Date(chat.updated_at || Date.now()),
            lastMessage: chat.last_message || "No messages yet",
          });
        });

        console.log(`✅ Loaded ${this.chats.size} chats into memory`); // DEBUG
        return true;
      } else {
        console.warn("⚠️ No chats found in response"); // DEBUG
        return false;
      }
    } catch (error) {
      console.error("❌ Error loading chats from backend:", error);
      return false;
    }
  }

  // FIXED: Dedicated method to load chat history
  async loadChatHistory(chatId) {
    if (!chatId) {
      console.error("❌ No chat ID provided to loadChatHistory");
      return false;
    }

    try {
      console.log(`🔍 Loading history for chat: ${chatId}`); // DEBUG

      const response = await fetch(
        `${this.API_BASE_URL}/chat-history/${chatId}`
      );

      if (!response.ok) {
        console.error(`❌ Failed to fetch chat history: ${response.status}`);
        return false;
      }

      const data = await response.json();
      console.log(`📚 Chat history data for ${chatId}:`, data); // DEBUG

      if (data.history && Array.isArray(data.history)) {
        const chat = this.chats.get(chatId);
        if (chat) {
          chat.messages = data.history.map((msg, index) => {
            console.log(`💌 Processing message ${index + 1}:`, msg); // DEBUG

            return {
              type: msg.role === "user" ? "user" : "ai",
              content: msg.content || "",
              timestamp: new Date(
                msg.timestamp || msg.created_at || Date.now()
              ),
            };
          });

          console.log(
            `✅ Loaded ${chat.messages.length} messages for chat ${chatId}`
          ); // DEBUG
          return true;
        } else {
          console.error(`❌ Chat ${chatId} not found in local storage`);
        }
      } else {
        console.log(`ℹ️ No message history found for chat ${chatId}`); // DEBUG
        return true; // Not an error - chat might be empty
      }
    } catch (error) {
      console.error(`❌ Error loading chat history for ${chatId}:`, error);
      return false;
    }

    return false;
  }

  // FIXED: Force UI update method
  forceUIUpdate() {
    console.log("🔄 Forcing UI update..."); // DEBUG
    console.log(`Current chat ID: ${this.currentChatId}`); // DEBUG
    console.log(`Current chat exists: ${this.chats.has(this.currentChatId)}`); // DEBUG

    if (this.currentChatId && this.chats.has(this.currentChatId)) {
      const currentChat = this.chats.get(this.currentChatId);
      console.log(`Current chat messages: ${currentChat.messages.length}`); // DEBUG
    }

    this.updateChatTitle();
    this.renderChatList();
    this.renderMessages();
  }

  // FIXED: Switch to chat method
  async switchToChat(chatId) {
    if (this.currentChatId === chatId) {
      console.log(`ℹ️ Already on chat ${chatId}`); // DEBUG
      return;
    }

    console.log(`🔄 Switching to chat: ${chatId}`); // DEBUG

    try {
      // Load chat history if not already loaded
      const chat = this.chats.get(chatId);
      if (chat && chat.messages.length === 0) {
        console.log(`📚 Loading history for chat ${chatId}...`); // DEBUG
        await this.loadChatHistory(chatId);
      }

      this.currentChatId = chatId;
      this.forceUIUpdate();

      // Close sidebar on mobile
      if (window.innerWidth <= 768) {
        this.closeSidebar();
      }

      console.log(`✅ Successfully switched to chat ${chatId}`); // DEBUG
    } catch (error) {
      console.error(`❌ Error switching to chat ${chatId}:`, error);
      this.showError("Failed to load chat history");
    }
  }

  // FIXED: Load user memory
  async loadUserMemory() {
    try {
      const response = await fetch(`${this.API_BASE_URL}/user-memory`);
      if (response.ok) {
        const data = await response.json();
        this.userMemory = data.memory || {};
        console.log("🧠 User memory loaded:", this.userMemory); // DEBUG
      }
    } catch (error) {
      console.error("❌ Error loading user memory:", error);
    }
  }

  // FIXED: Render chat list
  renderChatList() {
    console.log("📋 Rendering chat list..."); // DEBUG

    const chatList = document.getElementById("chatList");
    if (!chatList) {
      console.error("❌ Chat list element not found");
      return;
    }

    chatList.innerHTML = "";

    if (this.chats.size === 0) {
      console.log("ℹ️ No chats to render"); // DEBUG
      return;
    }

    // Sort chats by most recent first
    const sortedChats = Array.from(this.chats.values()).sort(
      (a, b) => b.updatedAt - a.updatedAt
    );

    console.log(`📊 Rendering ${sortedChats.length} chats`); // DEBUG

    sortedChats.forEach((chat, index) => {
      console.log(`📝 Rendering chat ${index + 1}: ${chat.id}`); // DEBUG

      const chatEntry = document.createElement("div");
      chatEntry.className = `chat-entry ${
        chat.id === this.currentChatId ? "active" : ""
      }`;
      chatEntry.setAttribute("data-chat-id", chat.id);
      chatEntry.setAttribute("tabindex", "0");

      const lastMessage =
        chat.lastMessage ||
        (chat.messages.length > 0
          ? chat.messages[chat.messages.length - 1].content.substring(0, 60) +
            "..."
          : "Start a conversation...");

      const timeStr = this.formatTime(chat.updatedAt);

      chatEntry.innerHTML = `
        <div class="chat-preview">
          <div class="chat-title">${this.escapeHtml(chat.title)}</div>
          <div class="chat-snippet">${this.escapeHtml(lastMessage)}</div>
        </div>
        <div class="chat-actions">
          <div class="chat-timestamp">${timeStr}</div>
          <button class="delete-chat-btn" onclick="app.deleteChat('${
            chat.id
          }')" title="Delete chat">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      `;

      chatEntry.addEventListener("click", (e) => {
        if (!e.target.closest(".delete-chat-btn")) {
          this.switchToChat(chat.id);
        }
      });

      chatEntry.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this.switchToChat(chat.id);
        }
      });

      chatList.appendChild(chatEntry);
    });

    console.log("✅ Chat list rendered successfully"); // DEBUG
  }

  // FIXED: Render messages with extensive debugging
  renderMessages() {
    console.log("💬 Rendering messages..."); // DEBUG

    const messagesContainer = document.getElementById("chatMessages");
    if (!messagesContainer) {
      console.error("❌ Messages container not found");
      return;
    }

    const currentChat = this.chats.get(this.currentChatId);
    console.log(`Current chat ID: ${this.currentChatId}`); // DEBUG
    console.log(`Current chat exists: ${!!currentChat}`); // DEBUG

    if (currentChat) {
      console.log(`Current chat has ${currentChat.messages.length} messages`); // DEBUG
    }

    if (!currentChat) {
      messagesContainer.innerHTML = `
        <div class="welcome-message">
          <div class="welcome-content">
            <h2>Welcome to Coworker V1</h2>
            <p>No chat selected. Please create a new chat or select an existing one.</p>
            <p><small>Debug: currentChatId = ${this.currentChatId}</small></p>
          </div>
        </div>
      `;
      return;
    }

    if (currentChat.messages.length === 0) {
      let memoryInfo = "";
      if (Object.keys(this.userMemory).length > 0) {
        memoryInfo = "<div class='user-memory'><h4>I remember:</h4><ul>";
        for (const [key, value] of Object.entries(this.userMemory)) {
          memoryInfo += `<li><strong>${key}:</strong> ${value}</li>`;
        }
        memoryInfo += "</ul></div>";
      }

      messagesContainer.innerHTML = `
        <div class="welcome-message">
          <div class="welcome-content">
            <h2>Welcome to Coworker V1</h2>
            <p>Your AI assistant is ready to help. I remember our previous conversations and will learn about you as we chat.</p>
            ${memoryInfo}
            <p><small>Debug: Chat "${currentChat.title}" has no messages</small></p>
          </div>
        </div>
      `;
      return;
    }

    messagesContainer.innerHTML = "";

    currentChat.messages.forEach((message, index) => {
      console.log(`💌 Rendering message ${index + 1}:`, message); // DEBUG
      const messageElement = this.createMessageElement(message, index);
      messagesContainer.appendChild(messageElement);
    });

    this.scrollToBottom();
    console.log(`✅ Rendered ${currentChat.messages.length} messages`); // DEBUG
  }

  createMessageElement(message, index) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${message.type}`;
    messageDiv.setAttribute("data-message-index", index);

    const avatar = message.type === "user" ? "U" : "AI";
    const timeStr = this.formatTime(message.timestamp);

    messageDiv.innerHTML = `
      <div class="message-avatar">${avatar}</div>
      <div class="message-bubble">
        <div class="message-content">${this.formatMessageContent(
          message.content
        )}</div>
        <div class="message-time">${timeStr}</div>
      </div>
    `;

    return messageDiv;
  }

  formatMessageContent(content) {
    content = this.escapeHtml(content);
    content = content.replace(
      /```(\w+)?\n([\s\S]*?)```/g,
      (match, lang, code) => {
        return `<pre><code class="language-${
          lang || "text"
        }">${code.trim()}</code></pre>`;
      }
    );
    content = content.replace(/`([^`]+)`/g, "<code>$1</code>");
    content = content.replace(/\n/g, "<br>");
    return content;
  }

  showAppLoading() {
    const chatMessages = document.getElementById("chatMessages");
    if (chatMessages) {
      chatMessages.innerHTML = `
        <div class="welcome-message">
          <div class="welcome-content">
            <div class="app-loading">
              <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
              </div>
              <p>Loading your conversations...</p>
            </div>
          </div>
        </div>
      `;
    }
  }

  hideAppLoading() {
    // Loading state will be replaced by renderMessages()
  }

  async createNewChat() {
    const chatId = `chat_${Date.now()}_${this.chatCounter++}`;
    const title = "New Conversation";

    console.log(`🆕 Creating new chat: ${chatId}`); // DEBUG

    try {
      const response = await fetch(`${this.API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chat_id: chatId,
          title: title,
        }),
      });

      const data = await response.json();

      if (data.success) {
        const chatData = {
          id: chatId,
          title: title,
          messages: [],
          createdAt: new Date(),
          updatedAt: new Date(),
        };

        this.chats.set(chatId, chatData);
        this.currentChatId = chatId;

        this.forceUIUpdate();
        this.clearInput();

        if (window.innerWidth <= 768) {
          this.closeSidebar();
        }

        console.log(`✅ New chat created: ${chatId}`); // DEBUG
      } else {
        this.showError("Failed to create new chat");
      }
    } catch (error) {
      console.error("❌ Error creating chat:", error);
      this.showError("Failed to create new chat");
    }
  }

  async sendMessage() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();

    if (!message || this.isLoading) return;

    this.isLoading = true;
    this.updateSendButton();

    this.addMessageLocally("user", message);
    this.clearInput();
    this.showLoader();

    try {
      const response = await fetch(`${this.API_BASE_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: message,
          chat_id: this.currentChatId,
        }),
      });

      const data = await response.json();
      this.hideLoader();

      if (response.ok && data.response) {
        this.addMessageLocally("ai", data.response);
        this.updateChatTitleFromFirstMessage(message);
        await this.loadUserMemory();
      } else {
        this.addMessageLocally(
          "ai",
          data.error || "Sorry, I encountered an error. Please try again."
        );
      }
    } catch (error) {
      console.error("API Error:", error);
      this.hideLoader();
      this.addMessageLocally(
        "ai",
        "Sorry, I couldn't connect to the server. Please check your connection and try again."
      );
    }

    this.isLoading = false;
    this.updateSendButton();
    input.focus();
  }

  addMessageLocally(type, content) {
    const currentChat = this.chats.get(this.currentChatId);
    if (!currentChat) return;

    const message = {
      type,
      content,
      timestamp: new Date(),
    };

    currentChat.messages.push(message);
    currentChat.updatedAt = new Date();

    this.renderMessages();
    this.renderChatList();
  }

  async updateChatTitleFromFirstMessage(firstMessage) {
    const currentChat = this.chats.get(this.currentChatId);
    if (!currentChat || currentChat.messages.length > 2) return;

    const title =
      firstMessage.length > 40
        ? firstMessage.substring(0, 40) + "..."
        : firstMessage;

    currentChat.title = title;

    try {
      await fetch(`${this.API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chat_id: this.currentChatId,
          title: title,
        }),
      });
    } catch (error) {
      console.error("Error updating chat title:", error);
    }

    this.updateChatTitle();
    this.renderChatList();
  }

  updateChatTitle() {
    const currentChat = this.chats.get(this.currentChatId);
    const titleElement = document.getElementById("activeChatTitle");

    if (currentChat && titleElement) {
      titleElement.textContent = currentChat.title;
    }
  }

  showLoader() {
    const loader = document.getElementById("loaderContainer");
    if (loader) {
      loader.classList.remove("hidden");
      this.scrollToBottom();
    }
  }

  hideLoader() {
    const loader = document.getElementById("loaderContainer");
    if (loader) {
      loader.classList.add("hidden");
    }
  }

  updateSendButton() {
    const sendBtn = document.getElementById("sendBtn");
    const input = document.getElementById("messageInput");

    if (sendBtn && input) {
      sendBtn.disabled = input.value.trim().length === 0 || this.isLoading;
    }
  }

  clearInput() {
    const input = document.getElementById("messageInput");
    if (input) {
      input.value = "";
      input.style.height = "auto";
      this.updateCharacterCount();
    }
  }

  scrollToBottom() {
    const container = document.getElementById("chatMessagesContainer");
    if (container) {
      setTimeout(() => {
        container.scrollTop = container.scrollHeight;
      }, 100);
    }
  }

  async deleteChat(chatId) {
    if (
      confirm(
        "Are you sure you want to delete this chat? This cannot be undone."
      )
    ) {
      try {
        const response = await fetch(`${this.API_BASE_URL}/chat/${chatId}`, {
          method: "DELETE",
        });

        const data = await response.json();

        if (data.success) {
          this.chats.delete(chatId);

          if (this.currentChatId === chatId) {
            if (this.chats.size > 0) {
              const remainingChats = Array.from(this.chats.values());
              this.currentChatId = remainingChats[0].id;
              await this.switchToChat(this.currentChatId);
            } else {
              await this.createNewChat();
            }
          }

          this.forceUIUpdate();
        } else {
          this.showError("Failed to delete chat");
        }
      } catch (error) {
        console.error("Error deleting chat:", error);
        this.showError("Failed to delete chat");
      }
    }
  }

  async clearAllChats() {
    if (
      confirm(
        "Are you sure you want to clear all chat history? This cannot be undone."
      )
    ) {
      try {
        const deletePromises = Array.from(this.chats.keys()).map((chatId) =>
          fetch(`${this.API_BASE_URL}/chat/${chatId}`, { method: "DELETE" })
        );

        await Promise.all(deletePromises);

        this.chats.clear();
        this.chatCounter = 1;
        await this.createNewChat();
      } catch (error) {
        console.error("Error clearing chats:", error);
        this.showError("Failed to clear all chats");
      }
    }
  }

  formatTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  showError(message) {
    console.error("🚨 Error:", message); // DEBUG

    const errorDiv = document.createElement("div");
    errorDiv.className = "error-notification";
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background-color: var(--danger-color);
      color: white;
      padding: 12px 16px;
      border-radius: 8px;
      z-index: 10000;
      animation: slideIn 0.3s ease-out;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;

    document.body.appendChild(errorDiv);

    setTimeout(() => {
      errorDiv.remove();
    }, 5000);
  }

  // Export/Search functionality (keeping existing methods)
  exportChat(chatId) {
    const chat = this.chats.get(chatId);
    if (!chat) return;

    const exportData = {
      title: chat.title,
      messages: chat.messages,
      exportedAt: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `coworker-chat-${chat.title.replace(/[^a-z0-9]/gi, "_")}.json`;
    a.click();

    URL.revokeObjectURL(url);
  }

  searchChats(query) {
    const searchTerm = query.toLowerCase();
    const chatList = document.getElementById("chatList");
    const entries = chatList.querySelectorAll(".chat-entry");

    entries.forEach((entry) => {
      const chatId = entry.getAttribute("data-chat-id");
      const chat = this.chats.get(chatId);

      if (chat) {
        const titleMatch = chat.title.toLowerCase().includes(searchTerm);
        const messageMatch = chat.messages.some((msg) =>
          msg.content.toLowerCase().includes(searchTerm)
        );

        entry.style.display = titleMatch || messageMatch ? "block" : "none";
      }
    });
  }
}

// Initialize the app when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  console.log("🌟 DOM loaded, creating CoworkerApp instance..."); // DEBUG
  window.app = new CoworkerApp();
});

// Utility functions
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Export for potential module use
if (typeof module !== "undefined" && module.exports) {
  module.exports = CoworkerApp;
}
