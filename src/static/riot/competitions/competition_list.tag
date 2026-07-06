<competition-list>
    <div class="workspace-shell">
        <div class="workspace-tabs">
            <div class="ui fluid secondary pointing tabular menu workspace-tab-menu">
                <a class="active item" data-tab="running">Created by me</a>
                <a class="item" data-tab="participating">Participating</a>
                <div class="right menu">
                    <div class="item workspace-help">
                        <help_button href="https://docs.codabench.org/latest/Organizers/Running_a_benchmark/Competition-Management-%26-List/"></help_button>
                    </div>
                </div>
            </div>
        </div>

        <div class="ui active tab" data-tab="running">
            <div class="workspace-list-head">
                <div class="workspace-count">{ (running_competitions || []).length } tests</div>
                <div class="workspace-note">Open a test to manage resources, submissions, or leaderboard settings.</div>
            </div>
            <div if="{ !(running_competitions || []).length }" class="workspace-empty">
                <h3>No tests created yet</h3>
                <p>Create your first test or upload an existing bundle to start managing evaluations here.</p>
            </div>
            <div if="{ (running_competitions || []).length }" class="workspace-card-grid">
                <div each="{ competition in running_competitions }" no-reorder class="workspace-card">
                    <div class="workspace-card-top">
                        <div class="workspace-card-title-block">
                            <a class="workspace-card-title" href="{ URLS.COMPETITION_DETAIL(competition.id) }">{ competition.title }</a>
                            <div class="workspace-card-meta">
                                <span class="workspace-chip">{ format_competition_type(competition.competition_type) }</span>
                                <span>{ timeSince(Date.parse(competition.created_when)) } ago</span>
                                <span class="{ published: competition.published, draft: !competition.published }">
                                    { competition.published ? 'Published' : 'Draft' }
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="workspace-card-actions">
                        <a href="{ URLS.COMPETITION_DETAIL(competition.id) }" class="ui button workspace-action ghost">
                            Open
                        </a>
                        <a href="{ URLS.COMPETITION_EDIT(competition.id) }" class="ui button workspace-action ghost">
                            Edit
                        </a>
                        <button class="ui button workspace-action ghost"
                                onclick="{ toggle_competition_publish.bind(this, competition) }">
                            { competition.published ? 'Unpublish' : 'Publish' }
                        </button>
                        <button class="ui button workspace-action danger"
                                onclick="{ delete_competition.bind(this, competition) }">
                            Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="ui tab" data-tab="participating">
            <div class="workspace-list-head">
                <div class="workspace-count">{ (participating_competitions || []).length } joined tests</div>
                <div class="workspace-note">Quick access to tests you are currently enrolled in.</div>
            </div>
            <div if="{ !(participating_competitions || []).length }" class="workspace-empty">
                <h3>No participating tests yet</h3>
                <p>Once you join or interact with a public test, it will appear here for faster access.</p>
            </div>
            <div if="{ (participating_competitions || []).length }" class="workspace-card-grid compact">
                <div each="{ competition in participating_competitions }" class="workspace-card participant-card">
                    <div class="workspace-card-top">
                        <div class="workspace-card-title-block">
                            <a class="workspace-card-title" href="{ URLS.COMPETITION_DETAIL(competition.id) }">{ competition.title }</a>
                            <div class="workspace-card-meta">
                                <span>{ timeSince(Date.parse(competition.created_when)) } ago</span>
                            </div>
                        </div>
                    </div>
                    <div class="workspace-card-actions">
                        <a href="{ URLS.COMPETITION_DETAIL(competition.id) }" class="ui button workspace-action ghost">
                            Open
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        var self = this

        self.one("mount", function () {
            self.update_competitions()
            $('.tabular.menu .item').tab();
        })

        self.update_competitions = function () {
            self.get_participating_in_competitions()
            self.get_running_competitions()
        }

        self.get_competitions_wrapper = function (query_params) {
            return CODALAB.api.get_competitions(query_params)
                .fail(function (response) {
                    toastr.error("Could not load competition list")
                })
        }

        self.get_participating_in_competitions = function () {
            self.get_competitions_wrapper({participating_in: true})
                .done(function (data) {
                    self.participating_competitions = data
                    self.update()
                })
        }

        self.get_running_competitions = function () {
            self.get_competitions_wrapper({
                mine: true,
                type: 'any',
            })
                .done(function (data) {
                    self.running_competitions = data
                    self.update()
                })
        }

        self.format_competition_type = function (type) {
            if (!type) return 'Test'
            if (type === 'benchmark') return 'Benchmark test'
            if (type === 'competition') return 'Standard test'
            return type
        }

        self.delete_competition = function (competition) {
            if (confirm("Are you sure you want to delete '" + competition.title + "'?")) {
                CODALAB.api.delete_competition(competition.id)
                    .done(function () {
                        self.update_competitions()
                        toastr.success("Competition deleted successfully")
                    })
                    .fail(function () {
                        toastr.error("Competition could not be deleted")
                    })
            }
        }

        self.toggle_competition_publish = function (competition) {
            CODALAB.api.toggle_competition_publish(competition.id)
                .done(function (data) {
                    var published_state = data.published ? "published" : "unpublished"
                    toastr.success(`Competition has been ${published_state} successfully`)
                    self.get_running_competitions()
                })
        }


    </script>
    <style type="text/stylus">
        .workspace-shell
            background #fff
            border-radius 28px
            border 1px solid rgba(27, 63, 106, 0.08)
            box-shadow 0 22px 40px rgba(16, 41, 71, 0.06)
            padding 24px

        .workspace-tabs
            margin-bottom 18px

        .workspace-tab-menu
            display flex !important
            align-items center
            gap 8px
            margin 0 !important
            border none !important

        .workspace-tab-menu .item
            border-radius 999px !important
            padding 12px 16px !important
            font-size 14px
            font-weight 700
            color #5a7394 !important
            margin 0 !important

        .workspace-tab-menu .active.item
            background rgba(29, 90, 167, 0.10) !important
            color #163a67 !important
            box-shadow inset 0 -2px 0 #1d5aa7

        .workspace-help
            padding-right 0 !important

        .workspace-list-head
            display flex
            justify-content space-between
            align-items center
            flex-wrap wrap
            gap 12px
            margin-bottom 18px

        .workspace-count
            color #14385f
            font-size 20px
            font-weight 800

        .workspace-note
            color #7a93b1
            font-size 13px

        .workspace-card-grid
            display grid
            grid-template-columns repeat(2, minmax(0, 1fr))
            gap 18px

        .workspace-card-grid.compact
            grid-template-columns repeat(2, minmax(0, 1fr))

        .workspace-card
            display flex
            flex-direction column
            justify-content space-between
            min-height 188px
            padding 22px
            border-radius 24px
            background linear-gradient(180deg, #ffffff, #f7fbff)
            border 1px solid rgba(29, 90, 167, 0.12)
            box-shadow 0 16px 30px rgba(16, 41, 71, 0.06)

        .participant-card
            min-height 156px

        .workspace-card-title-block
            display flex
            flex-direction column
            gap 12px

        .workspace-card-title
            color #12365f
            font-size 28px
            line-height 1.15
            font-weight 800

        .workspace-card-meta
            display flex
            flex-wrap wrap
            gap 10px 14px
            color #627d9f
            font-size 13px
            font-weight 700

        .workspace-chip
            display inline-flex
            align-items center
            padding 6px 10px
            border-radius 999px
            background #eef5fb
            color #1d5aa7

        .workspace-card-meta .published
            color #198754

        .workspace-card-meta .draft
            color #c46a00

        .workspace-card-actions
            display flex
            flex-wrap wrap
            gap 10px
            margin-top 22px

        .workspace-action.ui.button
            border-radius 999px
            padding 11px 16px
            font-size 13px
            font-weight 800
            box-shadow none

        .workspace-action.ghost
            background #fff
            color #1d5aa7
            border 1px solid rgba(29, 90, 167, 0.14)

        .workspace-action.danger
            background #fff5f5
            color #cf2e2e
            border 1px solid rgba(207, 46, 46, 0.16)

        .workspace-empty
            padding 34px 24px
            border-radius 22px
            background linear-gradient(180deg, #fbfdff, #f4f9ff)
            border 1px dashed rgba(29, 90, 167, 0.18)
            text-align center

        .workspace-empty h3
            margin 0 0 10px
            color #183f6d
            font-size 22px

        .workspace-empty p
            margin 0
            color #6c87a9
            font-size 14px
            line-height 1.7

        @media only screen and (max-width: 900px)
            .workspace-card-grid,
            .workspace-card-grid.compact
                grid-template-columns 1fr

        @media only screen and (max-width: 767px)
            .workspace-shell
                padding 18px

            .workspace-tab-menu
                flex-wrap wrap

            .workspace-tab-menu .right.menu
                width 100%
                justify-content flex-end

            .workspace-card-title
                font-size 24px

    </style>
</competition-list>
