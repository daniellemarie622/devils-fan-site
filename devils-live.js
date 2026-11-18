(() => {
    "use strict";

    const DATA_URL = "data/devils.json";

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value ?? "—";
    }

    function addCell(row, value, strong = false) {
        const cell = document.createElement("td");
        if (strong) {
            const bold = document.createElement("strong");
            bold.textContent = value ?? "—";
            cell.appendChild(bold);
        } else {
            cell.textContent = value ?? "—";
        }
        row.appendChild(cell);
    }

    function emptyMessage(container, message) {
        container.replaceChildren();
        const div = document.createElement("div");
        div.className = "empty-state";
        div.textContent = message;
        container.appendChild(div);
    }

    function renderArticles(id, articles, emptyText) {
        const container = document.getElementById(id);
        if (!container) return;
        container.replaceChildren();

        if (!Array.isArray(articles) || articles.length === 0) {
            emptyMessage(container, emptyText);
            return;
        }

        articles.forEach(article => {
            const card = document.createElement("article");
            card.className = "news-card";

            const heading = document.createElement("h4");
            const link = document.createElement("a");
            link.href = article.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = article.title || "Devils team update";
            heading.appendChild(link);
            card.appendChild(heading);

            if (article.date) {
                const date = document.createElement("p");
                date.textContent = article.date;
                card.appendChild(date);
            }

            container.appendChild(card);
        });
    }

    function renderSkaters(players) {
        const body = document.getElementById("skater-table");
        body.replaceChildren();

        if (!players || !players.length) {
            const row = body.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 10;
            cell.textContent = "No skater data is currently available.";
            return;
        }

        players.forEach(player => {
            const row = body.insertRow();
            addCell(row, player.number);
            addCell(row, player.name, true);
            addCell(row, player.position);
            addCell(row, player.games);
            addCell(row, player.goals);
            addCell(row, player.assists);
            addCell(row, player.points, true);
            addCell(row, player.plusMinus);
            addCell(row, player.pim);
            addCell(row, player.timeOnIce);
        });
    }

    function renderGoalies(players) {
        const body = document.getElementById("goalie-table");
        body.replaceChildren();

        if (!players || !players.length) {
            const row = body.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 9;
            cell.textContent = "No goaltending data is currently available.";
            return;
        }

        players.forEach(player => {
            const row = body.insertRow();
            addCell(row, player.number);
            addCell(row, player.name, true);
            addCell(row, player.games);
            addCell(row, player.wins);
            addCell(row, player.losses);
            addCell(row, player.overtimeLosses);
            addCell(row, player.goalsAgainstAverage);
            addCell(row, player.savePercentage);
            addCell(row, player.shutouts);
        });
    }

    function renderRosterChanges(changes) {
        const container = document.getElementById("roster-changes");
        container.replaceChildren();

        if (!changes || !changes.baselineExists) {
            emptyMessage(container, "The first automatic roster snapshot is being created. Future updates will show players newly listed or no longer listed on the NHL roster.");
            return;
        }

        const added = changes.newlyListed || [];
        const removed = changes.noLongerListed || [];

        if (!added.length && !removed.length) {
            emptyMessage(container, "No active-roster changes were detected since the previous scheduled update.");
            return;
        }

        const note = document.createElement("p");
        note.textContent = "These are roster-list differences, not confirmed assignments or call-ups. Check the official transaction headlines above for the exact move.";
        container.appendChild(note);

        [["Newly listed", added], ["No longer listed", removed]].forEach(([label, players]) => {
            const card = document.createElement("div");
            card.className = "news-card";
            const heading = document.createElement("h4");
            heading.textContent = label;
            card.appendChild(heading);

            if (!players.length) {
                const p = document.createElement("p");
                p.textContent = "None";
                card.appendChild(p);
            } else {
                players.forEach(player => {
                    const p = document.createElement("p");
                    p.textContent = (player.name || "Unknown player") +
                        (player.number ? " (#" + player.number + ")" : "");
                    card.appendChild(p);
                });
            }
            container.appendChild(card);
        });
    }

    async function loadDevilsData() {
        const timestamp = document.getElementById("last-updated");

        try {
            const response = await fetch(DATA_URL + "?v=" + Date.now(), {
                cache: "no-store"
            });
            if (!response.ok) throw new Error("Data file returned " + response.status);

            const data = await response.json();
            const standings = data.standings || {};

            setText("team-record",
                [standings.wins, standings.losses, standings.overtimeLosses]
                    .map(value => value ?? "—").join(" - "));
            setText("division-rank",
                standings.divisionRank ? standings.divisionRank + " " +
                    (standings.division || "Division") : "—");
            setText("team-points", standings.points ?? "—");
            setText("team-goals",
                (standings.goalsFor ?? "—") + " GF / " +
                (standings.goalsAgainst ?? "—") + " GA");

            renderSkaters(data.skaters || []);
            renderGoalies(data.goalies || []);
            renderArticles("injury-news", data.injuryReports,
                "No recent official injury-report articles were found.");
            renderArticles("transaction-news", data.transactions,
                "No recent official transaction articles were found.");
            renderArticles("team-news", data.news,
                "No recent official Devils news articles were found.");
            renderRosterChanges(data.rosterChanges);

            const practice = document.getElementById("practice-notes");
            practice.replaceChildren();
            if (data.practiceNotes && data.practiceNotes.length) {
                data.practiceNotes.forEach(article => {
                    const p = document.createElement("p");
                    const a = document.createElement("a");
                    a.href = article.url;
                    a.target = "_blank";
                    a.rel = "noopener noreferrer";
                    a.textContent = article.title;
                    a.style.color = "#ffffff";
                    p.appendChild(a);
                    practice.appendChild(p);
                });
            } else {
                const p = document.createElement("p");
                p.textContent = "See the latest official Devils notebook for confirmed practice lines and power-play combinations.";
                practice.appendChild(p);
            }

            const updated = data.updatedAt ? new Date(data.updatedAt) : null;
            timestamp.textContent = updated && !Number.isNaN(updated.getTime())
                ? "Data last refreshed: " + updated.toLocaleString()
                : "Data loaded; refresh time unavailable.";
        } catch (error) {
            console.error("Unable to load Devils data:", error);
            timestamp.textContent = "Live data is temporarily unavailable. The scheduled updater may not have completed yet.";
            ["skater-table", "goalie-table"].forEach(id => {
                const body = document.getElementById(id);
                body.replaceChildren();
                const row = body.insertRow();
                const cell = row.insertCell();
                cell.colSpan = id === "skater-table" ? 10 : 9;
                cell.textContent = "Data is not available yet. Please check again after the first successful update.";
            });
            ["injury-news", "transaction-news", "team-news", "roster-changes"].forEach(id => {
                emptyMessage(document.getElementById(id), "The first automatic update has not run yet.");
            });
        }
    }

    loadDevilsData();
})();
