<errors>
    <ul class="list">
        <li each="{ error_object, field in opts.errors }">
            <strong>{field}:</strong>

            <span each="{error in error_object}">
                <virtual if="{ error.constructor != Object }">
                    {error}
                </virtual>

                <virtual if="{ error.constructor == Object }">
                    <errors errors="{ error }"></errors>
                </virtual>
            </span>
        </li>
    </ul>
</errors>

<competition-form>
    <div class="competition-form-shell">
        <div class="competition-form-hero">
            <div>
                <div class="competition-form-eyebrow">Benchmark Setup</div>
                <h1>{ opts.competition_id ? 'Edit Benchmark' : 'Create Benchmark' }</h1>
                <p>Configure the benchmark details, participation rules, phases, leaderboard, and administrators in one guided workflow.</p>
            </div>
            <div class="competition-form-hero-actions">
                <a class="ui basic button" href="{ window.URLS.COMPETITION_MANAGEMENT }">
                    Back to Management
                </a>
            </div>
        </div>

        <div class="ui middle aligned stackable grid competition-form-grid">
            <div class="row centered">
                <div class="thirteen wide column">

                <div class="ui message error competition-form-error" show="{ Object.keys(errors).length > 0 }">
                    <div class="header">
                        Error(s) saving benchmark
                    </div>
                    <errors errors="{errors}"></errors>
                </div>

                    <div class="competition-form-panel">
                        <div class="ui six item secondary pointing menu competition-form-tabs">
                            <a class="active item" data-tab="competition_details">
                                Details
                                <i class="check circle green icon" show="{ section_valid.details }"></i>
                            </a>
                            <a class="item" data-tab="participation">
                                Participation
                                <i class="check circle green icon" show="{ section_valid.participation }"></i>
                            </a>
                            <a class="item" data-tab="pages">
                                Pages
                                <i class="check circle green icon" show="{ section_valid.pages }"></i>
                            </a>
                            <a class="item" data-tab="phases">
                                Phases
                                <i class="check circle green icon" show="{ section_valid.phases }"></i>
                            </a>
                            <a class="item" data-tab="leaderboard">
                                Leaderboard
                                <i class="check circle green icon" show="{ section_valid.leaderboard }"></i>
                            </a>
                            <a class="item" data-tab="collaborators">
                                Administrators
                                <i class="check circle green icon" show="{ section_valid.collaborators }"></i>
                            </a>
                        </div>

                        <div class="competition-form-body">
                            <div class="ui active tab" data-tab="competition_details">
                                <competition-details errors="{ errors.details }"></competition-details>
                            </div>
                            <div class="ui tab" data-tab="participation">
                                <competition-participation errors="{ errors.participation}"></competition-participation>
                            </div>
                            <div class="ui tab" data-tab="pages">
                                <competition-pages errors="{ errors.pages }"></competition-pages>
                            </div>
                            <div class="ui tab" data-tab="phases">
                                <competition-phases errors="{ errors.phases }"></competition-phases>
                            </div>
                            <div class="ui tab" data-tab="leaderboard">
                                <competition-leaderboards errors="{ errors.details }"></competition-leaderboards>
                            </div>
                            <div class="ui tab" data-tab="collaborators">
                                <competition-collaborators errors="{ errors.details }"></competition-collaborators>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="center aligned row">
                <div class="column">
                    <div class="competition-form-actions">
                        <div class="ui checkbox publish-checkbox">
                            <input type="checkbox" ref="publish">
                            <label>Publish</label>
                        </div>

                        <div class="competition-form-action-buttons">
                            <button class="ui primary button" onclick="{ save }">
                                Save
                            </button>

                            <button class="ui basic red button discard" onclick="{ discard }">
                                Discard Changes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

<script>
var self = this

self.competition = {}
self.errors = {}
self.section_valid = {
    details: false,
    participation: false,
    pages: false,
    phases: false,
    leaderboard: false,
    collaborators: true
}

self.save = function () {
    self.competition.published = self.refs.publish.checked

    var api_endpoint = self.opts.competition_id
        ? CODALAB.api.update_competition
        : CODALAB.api.create_competition

    var competition_return = Object.assign({}, self.competition)

    if (!competition_return.title) {
        var detail_tag = self.tags && self.tags["competition-details"]
        var detail_title = detail_tag && detail_tag.refs && detail_tag.refs.title
        if (detail_title && detail_title.value) {
            competition_return.title = detail_title.value.trim()
        }
    }

    if (!competition_return.title) {
        toastr.error("Title is missing. Enter a title in Details tab.")
        return
    }

    api_endpoint(competition_return, self.opts.competition_id)
        .done(function (response) {
            self.errors = {}
            toastr.success("Competition saved!")
            window.location.href = window.URLS.COMPETITION_DETAIL(response.id)
        })
        .fail(function (response) {
            self.errors = response.responseJSON || {}
            self.update()
            toastr.error("Error occurred while saving.")
        })
}

self.discard = function () {
    if (confirm('Discard changes?')) {
        window.location.href = window.URLS.COMPETITION_MANAGEMENT
    }
}

CODALAB.events.on('competition_data_update', function (data) {
    Object.assign(self.competition, data)
    self.update()
})

CODALAB.events.on('competition_is_valid_update', function (section, is_valid) {
    var section_key = section === 'leaderboards' ? 'leaderboard' : section
    if (Object.prototype.hasOwnProperty.call(self.section_valid, section_key)) {
        self.section_valid[section_key] = !!is_valid
        self.update()
    }
})

self.on('mount', function () {
    $('.competition-form-tabs .item', self.root).tab()

    if (self.opts.competition_id) {
        CODALAB.api.get_competition(self.opts.competition_id)
            .done(function (competition) {
                self.competition = competition || {}
                self.refs.publish.checked = !!self.competition.published
                CODALAB.events.trigger('competition_loaded', self.competition)
                self.update()
            })
            .fail(function () {
                toastr.error('Could not load existing competition settings.')
            })
    }
})
</script>

<style type="text/stylus">
    .competition-form-shell
        max-width 1240px
        margin 18px auto 28px
        padding 0 12px

    .competition-form-hero
        display flex
        align-items flex-start
        justify-content space-between
        gap 16px
        margin-bottom 18px
        padding 22px 26px
        border 1px solid rgba(15, 35, 95, 0.08)
        border-radius 20px
        background linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%)
        box-shadow 0 14px 36px rgba(18, 37, 77, 0.08)

    .competition-form-eyebrow
        margin-bottom 8px
        color #4f6b95
        font-size 12px
        font-weight 700
        letter-spacing 0.08em
        text-transform uppercase

    .competition-form-hero h1
        margin 0 0 8px
        color #163257
        font-size 30px
        font-weight 700

    .competition-form-hero p
        max-width 760px
        margin 0
        color #60728f
        line-height 1.6

    .competition-form-grid.ui.grid
        margin 0

    .competition-form-grid > .row
        padding-top 0

    .competition-form-panel
        border 1px solid rgba(15, 35, 95, 0.08)
        border-radius 20px
        overflow hidden
        background #ffffff
        box-shadow 0 18px 42px rgba(18, 37, 77, 0.08)

    .competition-form-error.ui.message
        border-radius 16px
        box-shadow 0 10px 26px rgba(214, 69, 69, 0.08)

    .competition-form-tabs.ui.pointing.menu
        margin 0
        padding 14px 14px 0
        border none
        background linear-gradient(180deg, #f7faff 0%, #eef4ff 100%)

    .competition-form-tabs.ui.pointing.menu .item
        margin 0 10px 0 0
        border none
        border-radius 14px 14px 0 0 !important
        background transparent
        color #5f7190
        font-weight 600
        transition background-color .18s ease, color .18s ease, box-shadow .18s ease

    .competition-form-tabs.ui.pointing.menu .item.active
        background #ffffff
        color #163257
        box-shadow 0 -1px 0 rgba(15, 35, 95, 0.05), 0 12px 24px rgba(18, 37, 77, 0.08)

    .competition-form-body
        padding 22px 24px 26px

    .competition-form-actions
        display flex
        align-items center
        justify-content space-between
        gap 14px
        margin-top 18px
        padding 18px 22px
        border 1px solid rgba(15, 35, 95, 0.08)
        border-radius 18px
        background #ffffff
        box-shadow 0 14px 32px rgba(18, 37, 77, 0.06)

    .competition-form-action-buttons
        display flex
        align-items center
        gap 10px
        justify-content flex-end

    .competition-form-shell .ui.button
        border-radius 12px
        font-weight 600

    .competition-form-shell .ui.primary.button
        background #2b7de9

    .competition-form-shell .ui.checkbox label
        color #516884
        font-weight 500

    .competition-form-shell .ui.form input,
    .competition-form-shell .ui.form textarea,
    .competition-form-shell .ui.dropdown,
    .competition-form-shell .ui.selection.dropdown
        border-radius 12px !important

    .competition-form-shell .ui.form input,
    .competition-form-shell .ui.form textarea
        border 1px solid rgba(28, 52, 95, 0.12)
        background #fbfdff
        box-shadow inset 0 1px 2px rgba(22, 50, 87, 0.04)

    @media (max-width: 900px)
        .competition-form-hero
            padding 18px

        .competition-form-hero h1
            font-size 25px

        .competition-form-body
            padding 18px

    @media (max-width: 700px)
        .competition-form-hero
            flex-direction column

        .competition-form-tabs.ui.pointing.menu
            padding 12px 12px 0
            overflow-x auto

        .competition-form-tabs.ui.pointing.menu .item
            white-space nowrap

        .competition-form-actions
            flex-direction column
            align-items stretch

        .competition-form-action-buttons
            justify-content stretch

        .competition-form-action-buttons > .ui.button
            flex 1 1 200px
</style>
</competition-form>
