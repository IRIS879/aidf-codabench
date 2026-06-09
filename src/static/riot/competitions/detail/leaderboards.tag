<leaderboards>
  <div class="lb-toolbar">
    <div class="ui left action input lb-search">
      <button type="button" class="ui icon button" id="search-leaderboard-button">
        <i class="search icon"></i>
      </button>
      <input ref="leaderboardFilter" type="text" placeholder="Filter Leaderboard by Columns" />
    </div>
    <a data-tooltip="Start typing to filter columns under 'Filter Leaderboard by Columns'" data-position="right center">
      <i class="question circle icon"></i>
    </a>

    <div class="lb-sort-group">
      <span class="lb-sort-label">Sort by</span>
      <div class="ui small buttons">
        <button
          type="button"
          class="ui button { active: sort_mode === 'score' }"
          onclick="{ set_sort_score }"
          title="Sort by primary score">
          <i class="sort amount down icon"></i> Score
        </button>
        <div class="or"></div>
        <button
          type="button"
          class="ui button { active: sort_mode === 'time' }"
          onclick="{ set_sort_time }"
          title="Sort by submission time (newest first)">
          <i class="clock icon"></i> Time
        </button>
      </div>
    </div>
  </div>

  <div class="ui segment" style="margin-top: 16px;">
    <table class="ui celled table coda-animated">
      <thead>
        <tr>
          <th class="center aligned" colspan="5"></th>
          <th each="{ task in filtered_tasks }" class="center aligned" colspan="{ task.colWidth }">
            { task.name }
          </th>
          <th if="{ opts.is_admin }"></th>
        </tr>

        <tr>
          <th class="center aligned">
            #
            <span class="lb-sort-indicator" if="{ sort_mode === 'score' }" title="Sorted by score">
              <i class="sort amount down icon"></i>
            </span>
            <span class="lb-sort-indicator" if="{ sort_mode === 'time' }" title="Sorted by time">
              <i class="clock icon"></i>
            </span>
          </th>
          <th>{ model_header }</th>
          <th>Date</th>
          <th>ID</th>
          <th>Model Card</th>
          <th each="{ column in filtered_columns }" colspan="1">{ column.title }</th>
          <th if="{ opts.is_admin }" class="center aligned">Delete</th>
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
            <a if="{ submission.slug_url }" href="{ submission.slug_url }">
              { get_model_name_ui_only(submission) }
            </a>
            <span if="{ !submission.slug_url }">
              { get_model_name_ui_only(submission) }
            </span>
          </td>

          <td>{ pretty_date(submission.created_when) }</td>
          <td>{ submission.id }</td>

          <td class="center aligned model-card-cell">
            <!-- Original uploaded file link (file-upload mode) -->
            <a if="{ submission.model_card_url }"
               href="{ submission.model_card_url }"
               target="_blank"
               rel="noopener"
               class="ui mini button mc-btn"
               title="View uploaded model card file">
              <i class="file icon"></i> File
            </a>

            <!-- PDF download (available for all submissions with model card data) -->
            <a if="{ submission.has_model_card }"
               href="{ '/api/submissions/' + submission.id + '/model-card/download/?dl=pdf' }"
               class="ui mini button mc-btn"
               title="Download model card as PDF">
              <i class="file pdf icon"></i> PDF
            </a>

            <!-- JSON download -->
            <a if="{ submission.has_model_card }"
               href="{ '/api/submissions/' + submission.id + '/model-card/download/?dl=json' }"
               class="ui mini button mc-btn"
               title="Download model card as JSON">
              <i class="file code icon"></i> JSON
            </a>

            <span if="{ !submission.model_card_url && !submission.has_model_card }">—</span>
          </td>

          <td each="{ column in filtered_columns }">
            <a if="{ column.title == 'Detailed Results' }" href="detailed_results/{ get_detailed_result_submisison_id(column, submission) }">
              View
            </a>
            <span if="{ column.title != 'Detailed Results' }">
              { get_submission_score(column, submission) }
            </span>
          </td>
          <td if="{ opts.is_admin }" class="center aligned">
            <button class="ui mini red icon button"
                    title="Delete submission"
                    onclick="{ delete_submission.bind(this, submission) }">
              <i class="trash icon"></i>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <script>
    let self = this;

    self.selected_leaderboard = { submissions: [] };
    self.raw_submissions = [];       // original order from API (score-sorted)
    self.sort_mode = 'score';        // 'score' | 'time'
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
      return submission.model_name || "Model";
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
          // Keep a pristine copy for re-sorting
          self.raw_submissions = (data && data.submissions) ? data.submissions.slice() : [];
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
          self.apply_sort();  // apply current sort mode before render

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
          return s.index === column.index || s.column_key === column.key;
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

    // ── Sorting ───────────────────────────────────────────────────────────────

    self.apply_sort = function () {
      if (!self.raw_submissions.length) return;

      let sorted = self.raw_submissions.slice();

      if (self.sort_mode === 'time') {
        // Newest submission first
        sorted.sort(function (a, b) {
          return new Date(b.created_when) - new Date(a.created_when);
        });
      } else {
        // By primary score (desc), NULL last, tiebreak: newest first
        let primary_index = (self.selected_leaderboard.primary_index != null)
          ? self.selected_leaderboard.primary_index
          : 0;

        sorted.sort(function (a, b) {
          let sa = Array.isArray(a.scores)
            ? a.scores.find(function (s) { return s.index === primary_index; })
            : null;
          let sb = Array.isArray(b.scores)
            ? b.scores.find(function (s) { return s.index === primary_index; })
            : null;

          let va = (sa && sa.score != null) ? parseFloat(sa.score) : null;
          let vb = (sb && sb.score != null) ? parseFloat(sb.score) : null;

          // NULL scores sink to the bottom
          if (va === null && vb === null) return new Date(b.created_when) - new Date(a.created_when);
          if (va === null) return 1;
          if (vb === null) return -1;

          // Higher score = better rank
          if (vb !== va) return vb - va;

          // Same score → newer submission first
          return new Date(b.created_when) - new Date(a.created_when);
        });
      }

      self.selected_leaderboard = Object.assign({}, self.selected_leaderboard, { submissions: sorted });
    };

    self.set_sort_score = function () {
      if (self.sort_mode === 'score') return;
      self.sort_mode = 'score';
      self.apply_sort();
      self.update();
    };

    self.set_sort_time = function () {
      if (self.sort_mode === 'time') return;
      self.sort_mode = 'time';
      self.apply_sort();
      self.update();
    };

    // ── Admin: Delete submission ──────────────────────────────────────────────

    self.delete_submission = function (submission) {
      let name = submission.model_name || ('ID ' + submission.id);
      if (!confirm('Delete submission "' + name + '" (#' + submission.id + ')?\nThis cannot be undone.')) return;

      CODALAB.api.delete_submission(submission.id)
        .then(function () {
          toastr.success('Submission #' + submission.id + ' deleted');
          // Remove from local list and re-render
          self.raw_submissions = self.raw_submissions.filter(function (s) {
            return s.id !== submission.id;
          });
          self.apply_sort();
          self.update();
        })
        .catch(function (err) {
          toastr.error('Delete failed: ' + (err.message || err));
        });
    };

  </script>

  <style type="text/stylus">
    :scope
      display block

    .index-column
      width 40px

    .model-card-cell
      white-space nowrap

    .mc-btn
      margin 2px 1px !important
      padding 4px 8px !important
      font-size 11px !important

    .lb-toolbar
      display flex
      align-items center
      flex-wrap wrap
      gap 12px
      margin-top 32px

    .lb-search
      width 33%
      min-width 200px

    .lb-sort-group
      display flex
      align-items center
      gap 8px
      margin-left auto

    .lb-sort-label
      font-size 13px
      color rgba(0,0,0,.5)
      white-space nowrap

    .lb-sort-indicator
      font-size 10px
      color rgba(0,0,0,.4)
      margin-left 2px
  </style>
</leaderboards>