 // JavaScript to manage time display, world clocks, and user interactions

let use24Hour = true;
let currentTime = "12:00:00";
let isEditing = false;
let lockRetryDelay = 500; // ms


function tryLock() {
  fetch('/lock', { method: 'POST' })
    .then(res => res.text())
    .then(response => {
      if (response.includes("LOCKED")) {
        console.log("Lock acquired!");
        isEditing = true;
      } else {
        console.log("Lock failed, retrying...");
        setTimeout(tryLock, lockRetryDelay);  // Retry after delay
      }
    })
    .catch(err => {
      console.error("Lock error:", err);
      setTimeout(tryLock, lockRetryDelay);  // Retry even on error
    });
}

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
  console.log("Updating local clock...");
  console.log("Current time before update:", currentTime);
  let [h, m, s] = currentTime.split(":").map(Number);
  s++;
  if (s >= 60) { s = 0; m++; }
  if (m >= 60) { m = 0; h++; }
  if (h >= 24) { h = 0; }
  currentTime = `${pad(h)}:${pad(m)}:${pad(s)}`;

  if (use24Hour) {
    document.getElementById("time").textContent = currentTime;
    document.getElementById("time_ampm").style.display = "none";
  } else {
    const { time, ampm } = formatTime24To12(currentTime);
    document.getElementById("time").textContent = time;
    document.getElementById("time_ampm").textContent = ampm;
    document.getElementById("time_ampm").style.display = "inline";
  }
}

function toggleTimeFormat() {

  use24Hour = !use24Hour;
  if (use24Hour) {
    document.getElementById("toggleFormat").style.backgroundColor = "green";
    document.getElementById("alarm_ampm").style.display = "none";}

  else {
    document.getElementById("toggleFormat").style.backgroundColor = "#007bff";
    document.getElementById("time_ampm").style.color = "#fff";
    document.getElementById("alarm_ampm").style.display = "inline";
  }
  
  updateLocalClock();  // Update the local clock display immediately
  if (isEditing) {return;}
  
  const data={ 
    use24Hour: use24Hour ? 1 : 0
  }
  fetch('/time_format', {
    method: "POST",   
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
  }).then(() => {
    console.log("Time format updated to " + (use24Hour ? "24-hour" : "12-hour"));
    
  }).catch(err => {
    console.error("Error updating time format:", err);
  });
  
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
  updateLocalClock();  // Update the local clock display immediately
  if (isEditing) {return;}
  
  const data = {
    localTime: currentTime
   };
  fetch('/set_local_time', {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
  }).then(() => {
    console.log("Local time set to " + currentTime);
  }).catch(err => {
    console.error("Error setting local time:", err);
  });
  
});

function updateWorldClocks() {
  try{
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
  }catch (error) {
  console.error("Error updating world clocks:", error); }
}

setInterval(() => {
  updateLocalClock();
  updateWorldClocks();
}, 1000);

// Button behaviors for Mute, Edit, Save, Volume


const volumeSlider = document.getElementById("volume");
const muteButton = document.getElementById("muteButton");
const editButton = document.getElementById("editButton");
const saveButton = document.getElementById("saveButton");
const alarm_hour = document.getElementById("alarm_hour");
const alarm_minute = document.getElementById("alarm_minute");
const alarm_ampm= document.getElementById("alarm_ampm");
const snoozeButton = document.getElementById("snooze");
const cancelAlarmButton = document.getElementById("cancelAlarm");
const freq1 = document.getElementById("freq1");
const freq2 = document.getElementById("freq2");
const freq3 = document.getElementById("freq3");


const choiceButtons = ['choice1', 'choice2', 'choice3'].map(id => document.getElementById(id));

choiceButtons.forEach(button => {
  
  button.addEventListener('click', () => {
    // Remove active class from all three
    choiceButtons.forEach(btn => btn.classList.remove('active'));
    // Add active class to the one clicked
    button.classList.add('active');
    if (isEditing) return; // Don't change choice while editing
    const choice = button.id.replace('choice', '');
    const data = { nowplaying: choice };
    fetch('/choice', {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    }).then(() => {
      console.log("Choice updated to " + choice);
    }
    ).catch(err => {
      console.error("Error updating choice:", err);
    });
  }
  );  
});


cancelAlarmButton.addEventListener("click", () => {
  
  if (cancelAlarmButton.value === "1") {
    cancelAlarmButton.style.backgroundColor = "red";
    cancelAlarmButton.style.color = "white";
    cancelAlarmButton.value = "0";  // Set to "0" to indicate alarm is cancelled
    
  }
  else {
    
    cancelAlarmButton.style.backgroundColor = "#007bff";
    cancelAlarmButton.style.color = "#fff";
    cancelAlarmButton.value = "1";  // Set to "1" to indicate alarm is active
  }


})

muteButton.addEventListener("click", () => {
  if (muteButton.value === "1") {
    // currently muted → unmute
    muteButton.value = "0";
    muteButton.style.backgroundColor = "#007bff";
    muteButton.style.color = "#fff";
    
  } else {
    // currently unmuted → mute
    muteButton.value = "1";
    muteButton.style.backgroundColor = "red";
    muteButton.style.color = "white";
  }

 
  if (isEditing) return; // Don't mute while editing
  
  const data = {
    mute: muteButton.value}
  fetch('/mute', {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    }).then(() => {
    console.log("Volume muted")});

})

volumeSlider.addEventListener("input", () => {
  if (isEditing) return; // Don't change volume while editing       
  
  const data = {
    volume: volumeSlider.value
  }
  fetch('/volume', {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    }).then(() => {
    console.log("Volume updated to " + volumeSlider.value)});
});
  


editButton.addEventListener("click", () => {
  isEditing = true;
  
  alarm_hour.disabled = false;
  alarm_minute.disabled = false;
  alarm_ampm.disabled = false;
  snoozeButton.disabled = false;
  cancelAlarmButton.disabled = false;
  freq1.disabled = false;
  freq2.disabled = false;
  freq3.disabled = false;
  choiceButtons.forEach(button => {
    button.disabled = false;  
    button.classList.remove('active');  // Remove active class from all choices
  });
  
  tryLock();  // Start trying to lock
  
  
  document.querySelector(".right-panel").style.backgroundColor = "#4d4b4bff";
});

saveButton.addEventListener("click", () => {
  if (!isEditing) return;
  isEditing = false;
  volumeSlider.disabled =false;
  alarm_ampm.disabled = true;
  alarm_hour.disabled = true;
  alarm_minute.disabled = true;
  freq1.disabled = true;
  freq2.disabled = true;
  freq3.disabled = true;
  snoozeButton.disabled = true;
  cancelAlarmButton.disabled = true;
  
  

  sendUpdate();  // Save changes
  fetch('/unlock', { method: 'POST' })
    .then(() => {
      isEditing = false;
      console.log("Lock released");
    });
  document.querySelector(".right-panel").style.backgroundColor = "#2c2c2c";

});




function sendUpdate() {
  let choice;
  if (document.getElementById("choice1").classList.contains('active')) {
    choice = 1;
  } else if (document.getElementById("choice2").classList.contains('active')) {
    choice = 2;
  } else if (document.getElementById("choice3").classList.contains('active')) {
    choice = 3; 
  }

  
  const data = {
    alarm_hour: alarm_hour.value,
    alarm_minute: alarm_minute.value,
    alarm_ampm: alarm_ampm.value,
    freq1: freq1.value,
    freq2: freq2.value,
    freq3: freq3.value,
    volume: volumeSlider.value,
    nowplaying: choice ? choice : 1,  // Default to choice 1 if none selected
    use24Hour: use24Hour ? 1 : 0,
    mute: muteButton.value,
    Time: currentTime,
    snooze: snoozeButton.value,
    cancelAlarm: cancelAlarmButton.value
  }

  fetch('/update', {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
  }).then(() => {
    console.log("Settings updated successfully");
  }).catch(err => {
    console.error("Error updating settings:", err);
  });

  


}




function fetchDataAndUpdateUI() {
  if (isEditing) return; // Don't overwrite while editing

  fetch('/data')
    .then(res => res.json())
    .then(data => {
      console.log("Fetched data:", data);
      // Update local clock
      currentTime = data.Time;
      // Update time format
      use24Hour = data.use24Hour === 1;
      document.getElementById("toggleFormat").style.backgroundColor = use24Hour ? "red" : "green";
      document.getElementById("time_ampm").style.display = use24Hour ? "none" : "inline";

     

      

      // Update mute button
      muteButton.value = data.mute;
      muteButton.style.backgroundColor = data.mute ? "red" : "green";
      muteButton.style.color = data.mute ? "white" : "black";

      // Update volume slider
      volumeSlider.value = data.volume;

      // Update alarm settings
      alarm_hour.value = data.alarm_hour;
      alarm_minute.value = data.alarm_minute;
      alarm_ampm.value = data.alarm_ampm;
      snoozeButton.value = data.snooze;
      cancelAlarmButton.value = data.cancelAlarm;

      // Update frequency choices
      freq1.value = data.freq1;
      freq2.value = data.freq2;
      freq3.value = data.freq3;
      choiceButtons.forEach(button => {
        button.classList.remove('active');
      });
      if (data.nowplaying === 1) {
        document.getElementById("choice1").classList.add('active');
      } else if (data.nowplaying === 2) {
        document.getElementById("choice2").classList.add('active');
      } else if (data.nowplaying === 3) {
        document.getElementById("choice3").classList.add('active');
      }
      
    });
}

setInterval(fetchDataAndUpdateUI, 2000);
