// StudentHub Portal Client Scripts

// Apply saved theme early (defaults to dark mode)
(function () {
    const saved = localStorage.getItem("theme");
    if (saved === "light") {
        document.body.classList.remove("dark-mode");
    } else {
        document.body.classList.add("dark-mode");
    }
})();

document.addEventListener("DOMContentLoaded", () => {
    // Theme toggle
    const themeBtn = document.getElementById("themeToggleBtn");
    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            const isDark = document.body.classList.toggle("dark-mode");
            localStorage.setItem("theme", isDark ? "dark" : "light");
            if (document.getElementById("statusChart")) {
                location.reload();
            }
        });
    }

    // Auto-clear flash notices
    document.querySelectorAll(".alert").forEach(el => {
        setTimeout(() => {
            el.style.opacity = "0";
            el.style.transition = "opacity 0.4s";
            setTimeout(() => el.remove(), 400);
        }, 3500);
    });

    // Real-time search with debounce
    const searchInput = document.getElementById("searchInput");
    const tableBody = document.getElementById("studentsTableBody");

    let timer = null;
    if (searchInput && tableBody) {
        searchInput.addEventListener("input", (e) => {
            clearTimeout(timer);
            const val = e.target.value.trim();

            timer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/students?search=${encodeURIComponent(val)}`);
                    if (!res.ok) return;
                    const data = await res.json();

                    if (data.length === 0) {
                        tableBody.innerHTML = `
                            <tr>
                                <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 36px;">
                                    No students match "${escape(val)}".
                                </td>
                            </tr>
                        `;
                        return;
                    }

                    const userRole = tableBody.getAttribute("data-user-role") || "";
                    const currentStudentId = parseInt(tableBody.getAttribute("data-user-student-id") || "0", 10);
                    const isAdmin = userRole === "Administrator";

                    tableBody.innerHTML = data.map(s => {
                        const toggleBtn = isAdmin ? `
                            <form method="POST" action="/student/toggle-status/${s.id}" style="display:inline;">
                                <button type="submit" class="btn btn-sm btn-secondary" style="padding: 2px 6px; font-size: 11px;" title="Switch Status">⇄</button>
                            </form>
                        ` : '';

                        let actionButtons = `<a href="/student/${s.id}" class="btn btn-sm btn-secondary">Profile</a>`;
                        if (isAdmin) {
                            actionButtons += `
                                <a href="/student/edit/${s.id}" class="btn btn-sm btn-secondary">Edit</a>
                                <form method="POST" action="/student/delete/${s.id}" style="display:inline;" onsubmit="return confirm('Remove student record?');">
                                    <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                                </form>
                            `;
                        } else if (currentStudentId && currentStudentId === s.id) {
                            actionButtons += `
                                <a href="/student/edit/${s.id}" class="btn btn-sm btn-secondary">Edit My Profile</a>
                            `;
                        }

                        return `
                        <tr>
                            <td><span style="font-family: monospace; color: var(--text-muted);">#${String(s.id).padStart(3, '0')}</span></td>
                            <td>
                                <div class="user-cell">
                                    <div class="avatar-circle avatar-color-${s.id % 6}">${s.name.slice(0, 2).toUpperCase()}</div>
                                    <div>
                                        <div class="user-meta-name">${escape(s.name)}</div>
                                        <div class="user-meta-sub">${escape(s.email)} &bull; <span style="color: var(--secondary); font-family: monospace;">@${escape(s.username || '')}</span></div>
                                    </div>
                                </div>
                            </td>
                            <td><span style="font-size: 13px; color: var(--text-secondary);">${escape(s.phone || '—')}</span></td>
                            <td><span style="font-size: 13px; color: var(--text-secondary);">${escape(s.gender || '—')}</span></td>
                            <td><span class="badge-course">${escape(s.course)}</span></td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <span class="status-pill ${s.status === 'Active' ? 'active' : 'inactive'}">
                                        <span class="dot"></span>
                                        ${s.status}
                                    </span>
                                    ${toggleBtn}
                                </div>
                            </td>
                            <td>
                                <div style="display: flex; gap: 5px;">
                                    ${actionButtons}
                                </div>
                            </td>
                        </tr>
                        `;
                    }).join("");
                } catch (err) {
                    console.error("Search request error:", err);
                }
            }, 200);
        });
    }

    // Attendance buttons
    window.setAttendance = (id, status, btn) => {
        const input = document.getElementById(`att_input_${id}`);
        if (input) input.value = status;
        const group = btn.closest(".att-group");
        if (group) {
            group.querySelectorAll(".att-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
        }
    };

    window.markAllPresent = () => {
        document.querySelectorAll(".att-row").forEach(row => {
            const sid = row.getAttribute("data-student-id");
            const btn = row.querySelector(".att-btn.present");
            if (btn) setAttendance(sid, "Present", btn);
        });
    };

    function escape(str) {
        if (!str) return '';
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }
});
