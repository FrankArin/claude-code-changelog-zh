(function () {
  "use strict";

  var root = document.documentElement;
  var body = document.body;
  var themeButton = document.getElementById("theme-toggle");

  function currentTheme() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  if (themeButton) {
    themeButton.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try {
        localStorage.setItem("theme", next);
      } catch (error) {}
    });
  }

  var langButtons = document.querySelectorAll("[data-set-lang]");
  function setLang(mode) {
    body.dataset.lang = mode;
    try {
      localStorage.setItem("lang-mode", mode);
    } catch (error) {}
    langButtons.forEach(function (button) {
      var active = button.dataset.setLang === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  if (langButtons.length) {
    var savedLang = "zh";
    try {
      savedLang = localStorage.getItem("lang-mode") || "zh";
    } catch (error) {}
    setLang(savedLang);
    langButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        setLang(button.dataset.setLang);
      });
    });
  }

  var GROUP_LABELS = {
    added: "新增",
    changed: "变更",
    improvements: "改进",
    fixes: "修复",
    other: "其他"
  };

  var searchInput = document.getElementById("search-input");
  var searchResults = document.getElementById("search-results");
  var versionList = document.getElementById("version-list");

  if (searchInput && searchResults && versionList) {
    var index = null;
    var loading = null;
    var timer = null;

    function loadIndex() {
      if (index) return Promise.resolve(index);
      if (loading) return loading;
      var base = body.dataset.base || "";
      loading = fetch(base + "/search/index.json")
        .then(function (response) {
          return response.json();
        })
        .then(function (data) {
          if (Array.isArray(data)) {
            index = data;
            return index;
          }
          if (data && Array.isArray(data.shards)) {
            return Promise.all(
              data.shards.map(function (year) {
                return fetch(base + "/search/" + year + ".json").then(function (response) {
                  return response.json();
                });
              })
            ).then(function (shards) {
              index = shards.reduce(function (all, shard) {
                return all.concat(shard);
              }, []);
              return index;
            });
          }
          index = [];
          return index;
        });
      return loading;
    }

    searchInput.addEventListener(
      "focus",
      function () {
        loadIndex().catch(function () {});
      },
      { once: true }
    );

    searchInput.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(runSearch, 120);
    });

    function runSearch() {
      var query = searchInput.value.trim().toLowerCase();
      if (!query) {
        searchResults.hidden = true;
        searchResults.innerHTML = "";
        versionList.hidden = false;
        return;
      }

      loadIndex()
        .then(function (rows) {
          var hits = rows
            .filter(function (row) {
              return (
                (row.zh || "").toLowerCase().indexOf(query) !== -1 ||
                (row.en || "").toLowerCase().indexOf(query) !== -1 ||
                (row.v || "").toLowerCase().indexOf(query) !== -1 ||
                (row.d || "").indexOf(query) !== -1
              );
            })
            .slice(0, 100);
          renderResults(hits);
        })
        .catch(function () {
          versionList.hidden = true;
          searchResults.hidden = false;
          searchResults.innerHTML = '<p class="empty">搜索索引加载失败。</p>';
        });
    }

    function renderResults(hits) {
      versionList.hidden = true;
      searchResults.hidden = false;
      searchResults.innerHTML = "";

      if (!hits.length) {
        var empty = document.createElement("p");
        empty.className = "empty";
        empty.textContent = "没有匹配结果。";
        searchResults.appendChild(empty);
        return;
      }

      var count = document.createElement("p");
      count.className = "search-count";
      count.textContent = "找到 " + hits.length + " 条";
      searchResults.appendChild(count);

      hits.forEach(function (hit) {
        var link = document.createElement("a");
        link.className = "search-hit";
        var anchor = String(hit.id || "").split(".").join("-");
        link.href = (body.dataset.base || "") + "/v/" + hit.v + "/#item-" + anchor;

        var meta = document.createElement("span");
        meta.className = "search-meta";
        meta.textContent =
          hit.v +
          " · " +
          (hit.d || "日期未知") +
          " · " +
          (GROUP_LABELS[hit.g] || hit.g);

        var text = document.createElement("span");
        text.className = "search-text";
        text.textContent = hit.zh || hit.en || "";

        link.appendChild(meta);
        link.appendChild(text);
        searchResults.appendChild(link);
      });
    }
  }
})();
