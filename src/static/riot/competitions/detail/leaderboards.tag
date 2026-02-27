<leaderboards>
    <div class="ui left action input" style="margin-top: 32px; width: 33%">
        <button type="button" class="ui icon button" id="search-leaderboard-button">
            <i class="search icon"></i>
        </button>
        <input ref="leaderboardFilter" type="text" placeholder="Filter Leaderboard by Columns">
    </div>
    <a data-tooltip="Start typing to filter columns under 'Filter Leaderboard by Columns'"
       data-position="right center">
        <i class="question circle icon"></i>
    </a>

    <div class="ui segment" style="margin-top: 16px;">
        <table class="ui celled table coda-animated">
            <thead>
            <tr>
                <th class="center aligned" colspan="4"></th>
                <th each="{ task in filtered_tasks }" class="center aligned" colspan="{ task.colWidth }">{ task.name }</th>
            </tr>
            <tr>
                <th class="center aligned">#</th>
                <th>{ participant_header }</th>
                <th>Date</th>
                <th>ID</th>
                <th each="{ column in filtered_columns }" colspan="1">{column.title}</th>
            </tr>
            </thead>

            <tbody>
            <tr if="{_.isEmpty(selected_leaderboard.submissions)}" class="center aligned">
                <td colspan="100%">
                    <em>No submissions have been added to this leaderboard yet!</em>
                </td>
            </tr>

            <tr each="{ submission, index in selected_leaderboard.submissions}">
                <td class="collapsing index-column center aligned">
                    <gold-medal if="{index + 1 === 1}"></gold-medal>
                    <silver-medal if="{index + 1 === 2}"></silver-medal>
                    <bronze-medal if="{index + 1 === 3}"></bronze-medal>
                    <fourth-place-medal if="{index + 1 === 4}"></fourth-place-medal>
                    <fifth-place-medal if="{index + 1 === 5}"></fifth-place-medal>
                    <virtual if="{index + 1 > 5}">{index + 1}</virtual>
                </td>

                <td>
                    <a href="{submission.slug_url}">
                        { submission.display_name || submission.owner }
                    </a>
                </td>

                <td>{ pretty_date(submission.created_when) }</td>
                <td>{submission.id}</td>

                <td each="{ column in filtered_columns }">
                    <a if="{column.title == 'Detailed Results'}"
                       href="detailed_results/{get_detailed_result_submisison_id(column, submission)}">
                        View
                    </a>
                    <span if="{column.title != 'Detailed Results'}">{ get_submission_score(column, submission) }</span>
                </td>
            </tr>
            </tbody>
        </table>
    </div>

    <script>
        let self = this
        self.selected_leaderboard = {}
        self.filtered_tasks = []
        self.columns = []
        self.filtered_columns = []
        self.phase_id = null
        self.competition_id = null
        self.enable_detailed_results = false
        self.show_detailed_results_in_leaderboard = false

        self.participant_header = 'Participant'

        self.pretty_date = function (date_string) {
            if (!!date_string) {
                return luxon.DateTime.fromISO(date_string).toFormat('yyyy-MM-dd HH:mm')
            } else {
                return ''
            }
        }

        self.on("mount" , function () {
            if (self.opts.competition && (self.opts.competition.enable_model_card_submission || self.opts.competition.leaderboard_use_model_name)) {
                self.participant_header = 'Model Name'
            } else {
                self.participant_header = 'Participant'
            }

            this.refs.leaderboardFilter.onkeyup = function (e) {
                self.filter_columns()
            }
            $('#search-leaderboard-button').click(function(e) {
                self.filter_columns()
            })
        })

        // existing helper functions below (unchanged)
        self.filter_columns = function () {
            if (!self.selected_leaderboard || !self.selected_leaderboard.columns) {
                return
            }
            let filter = (self.refs.leaderboardFilter && self.refs.leaderboardFilter.value || "").toLowerCase()
            if (!filter) {
                self.filtered_columns = self.columns
                self.update()
                return
            }
            self.filtered_columns = self.columns.filter(function(c) {
                return (c.title || "").toLowerCase().includes(filter)
            })
            self.update()
        }

        self.get_submission_score = function (column, submission) {
            if (!submission || !submission.scores) return ""
            let score = submission.scores.find(s => s.column === column.index)
            return score ? score.score : ""
        }

        self.get_detailed_result_submisison_id = function(column, submission) {
            // keep existing behavior
            return submission.id
        }
    </script>

    <style type="text/stylus">
        :scope
            display block

        .index-column
            width 40px
    </style>
</leaderboards>