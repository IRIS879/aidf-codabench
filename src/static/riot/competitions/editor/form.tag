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
    <div class="ui middle aligned stackable grid container">
        <div class="row centered">
            <div class="twelve wide column">

                <div class="ui message error" show="{ Object.keys(errors).length > 0 }">
                    <div class="header">
                        Error(s) saving benchmark
                    </div>
                    <errors errors="{errors}"></errors>
                </div>

                <div class="ui six item secondary pointing menu">
                    <a class="active item" data-tab="competition_details">
                        Details
                    </a>
                    <a class="item" data-tab="participation">Participation</a>
                    <a class="item" data-tab="pages">Pages</a>
                    <a class="item" data-tab="phases">Phases</a>
                    <a class="item" data-tab="leaderboard">Leaderboard</a>
                    <a class="item" data-tab="collaborators">Administrators</a>
                </div>

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

        <div class="center aligned row">
            <div class="column">
                <div class="ui checkbox publish-checkbox">
                    <input type="checkbox" ref="publish">
                    <label>Publish</label>
                </div>

                <button class="ui primary button" onclick="{ save }">
                    Save
                </button>

                <button class="ui basic red button discard" onclick="{ discard }">
                    Discard Changes
                </button>
            </div>
        </div>
    </div>

<script>
var self = this

self.competition = {}
self.errors = {}

self.save = function () {

    self.competition.published = self.refs.publish.checked

    var api_endpoint = self.opts.competition_id
        ? CODALAB.api.update_competition
        : CODALAB.api.create_competition

                        // to make errors clearer, move errors for "detail" page into the errors "details" key
                        var details_section_fields = [
                            'title',
                            'logo',
                            'training_mode',
                            'period_col',
                            'rolling_start_period',
                            'rolling_end_period',
                            'rolling_window_size',
                            'rolling_window_start_date',
                            'rolling_window_end_date'
                        ]
                        details_section_fields.forEach(function (field) {
                            if (errors[field]) {
                                // initialize section, if not already
                                errors.details = errors.details || []

    // =========================
    // FIX: Ensure title exists
    // =========================
    self.competition_return.title = (self.competition_return.title || "").trim()

    if (
        !self.competition_return.title &&
        self.tags &&
        self.tags["competition-details"] &&
        self.tags["competition-details"].refs &&
        self.tags["competition-details"].refs.title
    ) {
        self.competition_return.title =
            (self.tags["competition-details"].refs.title.value || "").trim()
    }

    if (!self.competition_return.title) {
        toastr.error("Title is missing. Enter a title in Details tab.")
        return
    }

    api_endpoint(self.competition_return, self.opts.competition_id)
        .done(function (response) {
            toastr.success("Competition saved!")
            window.location.href = window.URLS.COMPETITION_DETAIL(response.id)
        })
        .fail(function (response) {
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

self.on('mount', function () {
    $('.menu .item').tab()
})
</script>
</competition-form>