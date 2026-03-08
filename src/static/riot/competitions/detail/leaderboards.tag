<leaderboards>
  <div class="ui left action input" style="margin-top: 32px; width: 33%">
    <button type="button" class="ui icon button" id="search-leaderboard-button">
      <i class="search icon"></i>
    </button>
    <input ref="leaderboardFilter" type="text" placeholder="Filter Leaderboard by Columns" />
  </div>
  <a data-tooltip="Start typing to filter columns under 'Filter Leaderboard by Columns'" data-position="right center">
    <i class="question circle icon"></i>
  </a>

  <div class="ui segment" style="margin-top: 16px;">
    <table class="ui celled table coda-animated">
      <thead>
        <tr>
          <th class="center aligned" colspan="5"></th>
          <th each="{ task in filtered_tasks }" class="center aligned" colspan="{ task.colWidth }">
            { task.name }
          </th>
        </tr>

        <tr>
          <th class="center aligned">#</th>
          <th>{ model_header }</th>
          <th>Date</th>
          <th>ID</th>
          <th>Model Card</th>
          <th each="{ column in filtered_columns }" colspan="1">{ column.title }</th>
        </tr>
      </thead>

      <tbody>
        <tr if="{ _.isEmpty(selected_leaderboard.submissions) }" class="center aligned">
          <td colspan="100%">
            <em>No submissions have been added to this leaderboard yet!</em>
          </td>
        </tr>

        <tr each="{ submission, index in selected_leaderboard.submissions }">
          <td class="collapsing index-column center aligned">
            <gold-medal if="{ index + 1 === 1 }"></gold-medal>
            <silver-medal if="{ index + 1 === 2 }"></silver-medal>
            <bronze-medal if="{ index + 1 === 3 }"></bronze-medal>
            <fourth-place-medal if="{ index + 1 === 4 }"></fourth-place-medal>
            <fifth-place-medal if="{ index + 1 === 5 }"></fifth-place-medal>
            <virtual if="{ index + 1 > 5 }">{ index + 1 }</virtual>
          </td>

          <td>
            <a href="{ submission.slug_url }">
              { get_model_name_ui_only(submission) }
            </a>
          </td>

          <td>{ pretty_date(submission.created_when) }</td>
          <td>{ submission.id }</td>

          <td class="center aligned">
            { get_model_card_ui_only(submission) }
          </td>

          <td each="{ column in filtered_columns }">
            <a if="{ column.title == 'Detailed Results' }" href="detailed_results/{ get_detailed_result_submisison_id(column, submission) }">
              View
            </a>
            <span if="{ column.title != 'Detailed Results' }">
              { get_submission_score(column, submission) }
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <script>
    let self = this;

    self.selected_leaderboard = { submissions: [] };
    self.filtered_tasks = [];
    self.columns = [];
    self.filtered_columns = [];
    self.phase_id = null;
    self.model_header = "Model";

    self.pretty_date = function (date_string) {
      if (!!date_string) {
        return luxon.DateTime.fromISO(date_string).toFormat("yyyy-MM-dd HH:mm");
      }
      return "";
    };

    self.get_model_name_ui_only = function (submission) {
      return submission.filename || submission.name || "Model";
    };

    self.get_model_card_ui_only = function (submission) {
      if (submission.model_card_url) {
        return `<a href="${submission.model_card_url}" target="_blank">View</a>`;
      }
      return "—";
    };

    self.on("mount", function () {

      if (this.refs.leaderboardFilter) {
        this.refs.leaderboardFilter.onkeyup = function () {
          self.filter_columns();
        };
      }

      $("#search-leaderboard-button").off("click").on("click", function () {
        self.filter_columns();
      });

      self.phase_id = opts.phase_id || null;

      self.fetch_leaderboard();

      CODALAB.events.on("phase_selected", function (selected_phase) {
        if (!selected_phase) return;

        self.phase_id = selected_phase.id;
        self.fetch_leaderboard();
      });

    });

    self.fetch_leaderboard = function () {

      if (!self.phase_id) return;

      console.log("Fetching leaderboard for phase:", self.phase_id);

      fetch(`/api/phases/${self.phase_id}/get_leaderboard/`)
        .then(r => r.json())
        .then(data => {

          console.log("Leaderboard response:", data);

          self.selected_leaderboard = data || {};
          self.columns = [];

          if (data.tasks && data.tasks.length) {
            data.tasks.forEach(function (task) {
              if (task.columns) {
                task.columns.forEach(function (col) {
                  col.task_name = task.name;
                  self.columns.push(col);
                });
              }
            });
          }

          self.filtered_columns = self.columns.slice();
          self.rebuild_filtered_tasks();

          self.update();
        })
        .catch(err => {
          console.error("Leaderboard fetch failed:", err);
        });

    };

    self.rebuild_filtered_tasks = function () {

      let grouped = {};

      self.filtered_columns.forEach(function (column) {

        let taskName = column.task_name || "Main";

        if (!grouped[taskName]) {
          grouped[taskName] = {
            name: taskName,
            colWidth: 0
          };
        }

        grouped[taskName].colWidth += 1;
      });

      self.filtered_tasks = Object.keys(grouped).map(function (key) {
        return grouped[key];
      });

    };

    self.filter_columns = function () {

      if (!self.columns) return;

      let filter = ((self.refs.leaderboardFilter && self.refs.leaderboardFilter.value) || "").toLowerCase();

      if (!filter) {
        self.filtered_columns = self.columns.slice();
        self.rebuild_filtered_tasks();
        self.update();
        return;
      }

      self.filtered_columns = self.columns.filter(function (c) {
        return (c.title || "").toLowerCase().includes(filter);
      });

      self.rebuild_filtered_tasks();
      self.update();
    };

    self.get_submission_score = function (column, submission) {

      if (!submission || !submission.scores) return "";

      if (Array.isArray(submission.scores)) {

        let score = submission.scores.find(function (s) {
          return s.column === column.index || s.key === column.key;
        });

        return score ? score.score : "";
      }

      if (typeof submission.scores === "object") {
        return submission.scores[column.key] || "";
      }

      return "";
    };

    self.get_detailed_result_submisison_id = function (column, submission) {
      return submission.id;
    };

  </script>

  <style type="text/stylus">
    :scope
      display block

    .index-column
      width 40px
  </style>
</leaderboards>