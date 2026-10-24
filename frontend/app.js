document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);
  const form = $("chatForm"), input = $("userInput"), send = $("sendBtn");
  const messages = $("messagesList"), welcome = $("welcomeHero"), eventList = $("eventList");
  const conversation = $("conversation"), scrollLatestBtn = $("scrollLatestBtn");
  const sidebar = $("sidebar"), statusTitle = $("statusTitle"), modelLabel = $("activeModel");
  const createConversationId = () => window.crypto?.randomUUID?.() || "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => { const r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 3 | 8)).toString(16); });
  let conversationId = createConversationId(), chatEpoch = 0, activeRequest = null;
  const demoSeatRoutes = {"ai-summit-2026-bengaluru":[1,1],"ai-summit-2026-hyderabad":[1,2],"neon-nights-jazz-mumbai":[2,3],"cyber-defense-expo-delhi":[3,4],"world-symphony-gala-chennai":[4,5],"culinary-wine-expo-goa":[5,6]};
  const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  function isNearLatest() { return conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight < 96; }
  function updateScrollControl() { scrollLatestBtn.classList.toggle("hidden", messages.childElementCount < 2 || isNearLatest()); }
  function scrollConversationToLatest() { requestAnimationFrame(() => { conversation.scrollTo({ top: conversation.scrollHeight, behavior: "smooth" }); updateScrollControl(); }); }
  conversation.addEventListener("scroll", updateScrollControl, { passive: true });
  scrollLatestBtn.addEventListener("click", scrollConversationToLatest);

  function renderAnswer(text) {
    // Route demo-only ticket URLs into this prototype’s local seat view.
    text = String(text ?? "").replace(/https?:\/\/events\.example\.com\/([^/\s)]+)\/(?:tickets|seats|register|seat-map)/gi, (url, slug) => {
      const target = demoSeatRoutes[slug.toLowerCase()];
      return target ? `/seats?event_id=${target[0]}&schedule_id=${target[1]}` : url;
    });
    let safe = escapeHTML(text);
    safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/seats\?[^\s)]+)\)/g, '<a class="chat-event-link" href="$2" target="_self" rel="noopener noreferrer">$1 ↗</a>');
    safe = safe.replace(/(^|[\s>])(https?:\/\/[^\s<]+)/g, '$1<a class="chat-event-link" href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
    safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g,"<code>$1</code>");
    return safe.split(/\n{2,}/).map(block => {
      const lines = block.split("\n");
      if (lines.every(line => /^\s*[-•*]\s+/.test(line))) return "<ul>" + lines.map(line => `<li>${line.replace(/^\s*[-•*]\s+/,"")}</li>`).join("") + "</ul>";
      return `<p>${lines.join("<br>")}</p>`;
    }).join("");
  }
  function addMessage(role, text, loading = false) {
    const row = document.createElement("article"); row.className = `message ${role}-msg`;
    const avatar = role === "user" ? "Y" : "✳";
    row.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-main"><div class="message-label">${role === "user" ? "You" : "Chartbot"}</div><div class="message-body">${loading ? '<span class="typing"><i></i><i></i><i></i></span>' : role === "user" ? escapeHTML(text).replace(/\n/g,"<br>") : renderAnswer(text)}</div></div>`;
    messages.appendChild(row); scrollConversationToLatest(); return row;
  }
  function newChat() {
    const oldConversationId = conversationId;
    conversationId = createConversationId();
    chatEpoch++;
    activeRequest?.abort(); activeRequest = null; send.disabled = false;
    messages.replaceChildren(); welcome.classList.remove("hidden"); input.value=""; input.style.height="auto";
    conversation.scrollTo({ top: 0, behavior: "auto" }); scrollLatestBtn.classList.add("hidden"); input.focus();
    if (oldConversationId) fetch("/api/chat/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ conversation_id: oldConversationId }), keepalive: true }).catch(() => {});
  }
  $("clearChatBtn").addEventListener("click", newChat); $("clearTopBtn").addEventListener("click", newChat);
  document.querySelectorAll("[data-query]").forEach(button => button.addEventListener("click", () => { input.value=button.dataset.query; form.requestSubmit(); sidebar.classList.remove("open"); }));
  input.addEventListener("input", () => { input.style.height="auto"; input.style.height=Math.min(input.scrollHeight,140)+"px"; });
  input.addEventListener("keydown", event => { if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();form.requestSubmit();} });
  form.addEventListener("submit", async event => {
    event.preventDefault(); const question=input.value.trim(); if(!question||send.disabled)return;
    const requestEpoch = chatEpoch, requestController = new AbortController(); activeRequest = requestController;
    welcome.classList.add("hidden"); addMessage("user",question); input.value="";input.style.height="auto";send.disabled=true;
    const pending=addMessage("bot","",true);
    try {
      const response=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:question,conversation_id:conversationId}),signal:requestController.signal});
      const data=await response.json(); if(!response.ok)throw new Error(data.detail||"The chat service could not answer right now.");
      if(requestEpoch!==chatEpoch)return;
      pending.remove();addMessage("bot",data.response||"I couldn’t find an answer in the event data.");
    } catch(error) { if(requestEpoch!==chatEpoch||error.name==="AbortError")return; pending.remove();addMessage("bot",`I couldn’t reach the event assistant. ${error.message||"Please try again."}`); }
    finally { if(requestEpoch===chatEpoch){activeRequest=null;send.disabled=false;input.focus();} }
  });
  async function fetchHealth(){try{const res=await fetch("/api/health");if(!res.ok)throw 0;const data=await res.json();statusTitle.textContent=data.llm_engine?.ollama_available?"Ollama connected":"Ollama offline · event data ready";modelLabel.textContent=data.llm_engine?.active_model||data.llm_engine?.target_model||"Ollama · Llama";}catch{statusTitle.textContent="Waiting for local service";}}
  async function fetchEvents(){eventList.innerHTML='<div class="side-loading">Loading events…</div>';try{const res=await fetch("/api/events");if(!res.ok)throw 0;const rows=await res.json();const grouped=new Map();for(const event of rows){const key=event.name||event.event_name;if(!key)continue;if(!grouped.has(key))grouped.set(key,{name:key,category:event.category||"Live event",cities:[]});const item=grouped.get(key);if(event.city&&!item.cities.includes(event.city))item.cities.push(event.city);}eventList.replaceChildren();[...grouped.values()].slice(0,8).forEach(event=>{const button=document.createElement("button");button.className="event-link";button.type="button";const title=document.createElement("span");title.className="event-name";title.textContent=event.name;const meta=document.createElement("span");meta.className="event-meta";meta.textContent=[event.category,event.cities.join(" · ")||"India"].join(" · ");button.append(title,meta);button.addEventListener("click",()=>{input.value=`Tell me about ${event.name}: dates, venue, tickets, and booking link`;form.requestSubmit();});eventList.append(button);});if(!eventList.childElementCount)eventList.innerHTML='<div class="side-loading">No events to show yet</div>';}catch{eventList.innerHTML='<div class="side-loading">Events will appear when the service is ready</div>';}}
  $("refreshEventsBtn").addEventListener("click",fetchEvents);$("menuBtn").addEventListener("click",()=>sidebar.classList.toggle("open"));
  async function loadSeatPage() {
    const params = new URLSearchParams(location.search);
    const eventId = Number(params.get("event_id")), scheduleId = Number(params.get("schedule_id"));
    if (!eventId || !scheduleId) return;
    $("welcomeHero").classList.add("hidden"); $("messagesList").classList.add("hidden"); $("conversation").classList.add("hidden"); $("seatPage").classList.remove("hidden"); $("composer-area")?.classList.add("hidden"); document.querySelector(".composer-area").classList.add("hidden");
    try {
      const response = await fetch(`/api/seats-page?event_id=${eventId}&schedule_id=${scheduleId}`);
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not load this event.");
      const e = data.event; $("seatEventName").textContent = e.name; $("seatEventMeta").textContent = `${e.venue_name} · ${e.city}, ${e.state} · ${e.event_date} · ${e.start_time}–${e.end_time}`;
      const ticketOptions = $("ticketOptions"); ticketOptions.replaceChildren();
      for (const ticket of data.tickets) { const card = document.createElement("article"); card.className = "ticket-option"; const name=document.createElement("strong");name.textContent=ticket.tier_name;const price=document.createElement("b");price.textContent=new Intl.NumberFormat("en-IN",{style:"currency",currency:ticket.currency||"INR",maximumFractionDigits:0}).format(ticket.price);const avail=document.createElement("span");avail.className="availability-tag";avail.textContent=ticket.tickets_available>0?`${ticket.tickets_available} available`:"Sold out";const perks=document.createElement("p");perks.textContent=ticket.perks||"Event admission";card.append(name,price,avail,perks);ticketOptions.append(card); }
      const sections = new Map(); for(const seat of data.seats){ if(!sections.has(seat.section))sections.set(seat.section,[]);sections.get(seat.section).push(seat); }
      const sectionRoot=$("seatSections");sectionRoot.replaceChildren();for(const [section,seats] of sections){const group=document.createElement("div");group.className="seat-section";const heading=document.createElement("div");heading.className="seat-section-heading";const title=document.createElement("strong");title.textContent=section;const count=document.createElement("span");count.textContent=`${seats.length} seats`;heading.append(title,count);const list=document.createElement("div");list.className="seat-code-list";for(const seat of seats){const chip=document.createElement("span");chip.className="seat-code"+(seat.is_accessible?" accessible":"");chip.textContent=seat.seat_code;chip.title=`${seat.row_num}, seat ${seat.seat_number}${seat.is_accessible?" · Accessible":""}`;list.append(chip);}group.append(heading,list);sectionRoot.append(group);}
      if(!data.tickets.length)ticketOptions.innerHTML="<p>No ticket tiers are listed for this session.</p>";if(!data.seats.length)sectionRoot.innerHTML="<p>Seat details are not available for this session.</p>";
    } catch(error) { $("seatEventName").textContent="Seats couldn’t be loaded";$("seatEventMeta").textContent=error.message||"Try again from the event chat."; }
  }
  fetchHealth();fetchEvents();loadSeatPage();setInterval(fetchHealth,30000);
});
