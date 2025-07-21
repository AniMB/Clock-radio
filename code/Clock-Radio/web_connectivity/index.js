// JavaScript to manage time display, world clocks, and user interactions

let use24Hour = true;
let currentTime = "12:00:00";

function pad(n) {
  return n < 10 ? '0' + n : n;
}

function formatTime24To12(time24) {
  let [h, m, s] = time24.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12;
  h = h ? h : 12; // 0 => 12
  return { time: `${pad(h)}:${pad(m)}:${pad(s)}`, ampm };
}

function updateLocalClock() {
  let [h, m, s] = currentTime.split(":".map(Number));
  s++;
  if (s >= 60) { s = 0; m++; }
  if (m >= 60) { m = 0; h++; }
  if (h >= 24) { h = 0; }
  currentTime = `${pad(h)}:${pad(m)}:${pad(s)}`;

  if (use24Hour) {
    document.getElementById("time").value = currentTime;
    document.getElementById("time_ampm").style.display = "none";
  } else {
    const { time, ampm } = formatTime24To12(currentTime);
    document.getElementById("time").value = time;
    document.getElementById("time_ampm").value = ampm;
    document.getElementById("time_ampm").style.display = "inline";
  }
}

function toggleTimeFormat() {
  use24Hour = !use24Hour;
   document.getElementById("alarm_ampm").style.display = "none";
}

document.getElementById("toggleFormat").addEventListener("click", toggleTimeFormat);

function getTimeInZone(timeZone) {
  const options = {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  };
  return new Intl.DateTimeFormat('en-US', options).format(new Date());
}

document.getElementById("setLT").addEventListener("click", () => {
  const tz = document.getElementById("timezone").value;
  currentTime = getTimeInZone(tz);
});

function updateWorldClocks() {
  const cities = {
    "Mumbai": "Asia/Kolkata",
    "Toronto": "America/Toronto",
    "London": "Europe/London",
    "Sydney": "Australia/Sydney",
    "Tokyo": "Asia/Tokyo",
    "Cancun": "America/Cancun"
  };
  for (const [city, tz] of Object.entries(cities)) {
    const time = getTimeInZone(tz);
    document.getElementById(`clock-${city}`).textContent = time;
  }
}

setInterval(() => {
  updateLocalClock();
  updateWorldClocks();
}, 1000);

// Button behaviors for Mute, Edit, Save, Volume
let editMode = false;

const volumeSlider = document.getElementById("volume");
const muteButton = document.getElementById("muteButton");
const editButton = document.getElementById("editButton");
const saveButton = document.getElementById("saveButton");
const timeInput = document.getElementById("time");
const ampmSelect = document.getElementById("time_ampm");

muteButton.addEventListener("click", () => {
  volumeSlider.value = 0;
});

editButton.addEventListener("click", () => {
  editMode = true;
  volumeSlider.disabled = false;
  timeInput.disabled = false;
  ampmSelect.disabled = !use24Hour ? false : true;
});

saveButton.addEventListener("click", () => {
  editMode = false;
  volumeSlider.disabled = true;
  timeInput.disabled = true;
  ampmSelect.disabled = true;

  const newTime = document.getElementById("time").value;
  const ampm = document.getElementById("time_ampm").value;

  if (!use24Hour) {
    let [h, m, s] = newTime.split(":".map(Number));
    if (ampm === "PM" && h < 12) h += 12;
    if (ampm === "AM" && h === 12) h = 0;
    currentTime = `${pad(h)}:${pad(m)}:${pad(s)}`;
  } else {
    currentTime = newTime;
  }
});
