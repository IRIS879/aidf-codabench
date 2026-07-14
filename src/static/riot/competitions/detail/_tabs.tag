<comp-tabs>
    <div class="ui grid comp-tabs">
        <!-- Tab menu -->
        <div class="ui tiny fluid four secondary pointing tabular menu details-menu">
            <div class="item" data-tab="pages-tab">Overview</div>
            <div class="item" data-tab="phases-tab">Schedule</div>
            <div class="item" data-tab="participate-tab">Submit</div>
            <div class="item" data-tab="results-tab">Leaderboard</div>
            <a if="{ competition.forum_enabled }" class="item" href="{URLS.FORUM(competition.forum)}">Forum</a>
            <div class="right menu">
                <div class="item">
                    <help_button href="https://docs.codabench.org/latest/Organizers/Running_a_benchmark/Competition-Detail-Page/"
                                 tooltip_position="left center"></help_button>
                </div>
            </div>
        </div>

        <!--Get Started tab-->
        <div class="pages-tab ui tab" data-tab="pages-tab">
            <div show="{loading}">
                <loader></loader>
            </div>
            <div class="ui relaxed grid" show="{!loading}">
                <div class="row">
                    <div class="four wide column">
                        <div class="ui side vertical tabular pages-menu menu">
                            <div each="{ page, i in competition.pages }" class="{active: i === 0} item"
                                 data-tab="_tab_page{page.index}">
                                { page.title }
                            </div>
                            <div if="{competition_has_no_terms_page()}" class="item"
                                 data-tab="_tab_page_term">
                                Terms
                            </div>
                            <div class="{active: _.get(competition.pages, 'length') === 0} item" data-tab="files">
                                Resources
                            </div>
                        </div>
                    </div>
                    <div class="twelve wide column">
                        <!-- Competition Pages  -->
                        <div each="{ page, i in competition.pages }" class="ui {active: i === 0} tab"
                             data-tab="_tab_page{page.index}">
                            <div class="ui" id="page_{i}">
                            </div>
                        </div>
                        <!--  Terms page  -->
                        <div if="{competition_has_no_terms_page()}" class="ui tab" data-tab="_tab_page_term">
                            <div class="ui" id="page_term">
                            </div>
                        </div>

                        <!--  Files page  -->
                        <div class="ui tab {active: _.get(competition.pages, 'length') === 0}" data-tab="files">
                            <div class="ui" id="files">
                                <div class="ui info message resources-message">
                                    <div class="header">Submission Resources</div>
                                    <p>Download a real baseline submission package here before preparing your submission.</p>
                                    <div class="resources-group">
                                        <div class="resources-group-title">Sample Submission Package</div>
                                        <div class="ui small buttons resource-buttons">
                                            <a class="ui button"
                                               href="{ get_sample_submission_url() }"
                                               target="_blank"
                                               rel="noopener noreferrer">
                                                <i class="download icon"></i>
                                                Baseline Logistic Regression Sample
                                            </a>
                                        </div>
                                    </div>
                                </div>
                                <!--  Login message if not loggedin  -->
                                <div if="{!CODALAB.state.user.logged_in}" class="ui yellow message">
                                    <a href="{URLS.LOGIN}?next={location.pathname}">Log In</a> or
                                    <a href="{URLS.SIGNUP}" target="_blank">Sign Up</a> to view availbale files.
                                </div>

                                <!--  Files table if loggedin  -->
                                <table if="{CODALAB.state.user.logged_in}" class="ui celled table">
                                    <thead>
                                    <tr>
                                        <th class="index-column">Download</th>
                                        <th>Phase</th>
                                        <th>Task</th>
                                        <th>Type</th>
                                        <th if="{competition.is_admin}">Available <span class="ui mini circular icon button"
                                                          data-tooltip="Available for download to participants."
                                                          data-position="top center">
                                                          <i class="question icon"></i>
                                                      </span>
                                        </th>
                                        <th>Size</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    <tr class="file_row" each="{file in competition.files}">
                                        <td>
                                            <a href="{URLS.DATASET_DOWNLOAD(file.key)}">
                                                <div class="ui button">{file.name}</div>
                                            </a>
                                        </td>
                                        <td>{file.phase}</td>
                                        <td>{file.task}</td>
                                        <td>{file.type}</td>
                                        <!--  <td>{file.type === 'Public Data' || file.type === 'Starting Kit' ? 'yes': 'no'}</td>  -->
                                        <td if="{competition.is_admin}" class="center aligned">
                                            <i if="{file.available}" class="checkmark box icon green"></i>
                                        </td>
                                        <td>{pretty_bytes(file.file_size)}</td>
                                    </tr>
                                    <!-- Conditional row if no files to show -->
                                    <tr class="center aligned">
                                        <td if = {competition.files === undefined ||competition.files.length === 0} colspan="100%">
                                            <em>No Files Available Yet</em>
                                        </td>
                                    </tr>
                                    </tbody>
                                </table>

                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!--Phases tab-->
        <div class="phases-tab ui tab" data-tab="phases-tab">
            <div show="{loading}">
                <loader></loader>
            </div>
            <div class="ui relaxed grid" show="{!loading}">
                <div class="row">
                    <div class="sixteen wide centered column">
                        <div class="ui styled accordion">
                            <virtual each="{ phase, i in competition.phases }">
                                <div class="ui teal phase-header title {active: selected_phase_index === phase.id}">
                                    <i class="ui dropdown icon"></i>
                                    {phase.name}
                                </div>
                                <div class="ui bottom attached content {active: selected_phase_index === phase.id}">
                                    <div class="phase-label">Start:</div>
                                    <div class="phase-info">{pretty_date(phase.start)}</div>
                                    <div class="phase-label">End:</div>
                                    <div class="phase-info">{pretty_date(phase.end)}</div>
                                    <span class="phase-label">Description: </span>
                                    <div class="phase-markdown" id="phase_{i}"></div>
                                </div>
                            </virtual>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Submissions tab-->
        <div class="submission-tab ui tab" data-tab="participate-tab">
            <!-- Tab Content !-->
            <div show="{loading}">
                <loader></loader>
            </div>

            <div show="{!loading}">
                <div if="{competition.participant_status === 'approved'}">
                    <div class="ui button-container">
                        <div class="ui inline button {active: selected_phase_index == phase.id}"
                             each="{ phase in competition.phases }"
                             onclick="{ phase_selected.bind(this, phase) }">{ phase.name }
                        </div>
                    </div>
                    <div>
                        <submission-limit></submission-limit>
                        <submission-upload is_admin="{competition.is_admin}" competition="{ competition }" phases="{ competition.phases }" fact_sheet="{ competition.fact_sheet }"></submission-upload>
                    </div>
                    <div>
                        <submission-manager id="user-submission-table" competition="{ competition }"></submission-manager>
                    </div>
                </div>
                <div if="{competition.participant_status !== 'approved'}">
                    <registration></registration>
                </div>
            </div>
        </div>

        <!-- Leaderboard tab-->
        <div class="results-tab ui tab" data-tab="results-tab">
            <div show="{loading}">
                <loader></loader>
            </div>
            <!-- Tab Content !-->
                <div show="{!loading}" class="results-shell">
                    <div class="leaderboard-topbar">
                        <div class="ui button-container inline leaderboard-phase-group">
                            <div class="ui button {active: selected_phase_index == phase.id}"
                                 each="{ phase in competition.phases }"
                                 onclick="{ phase_selected.bind(this, phase) }">{ phase.name }
                            </div>
                        </div>
                        <div show="{competition.admin}" class="leaderboard-admin-actions">
                            <a href="{ get_phase_leaderboard_pdf_url() }"
                               target="new"
                               class="ui primary button leaderboard-pdf-button">
                                <i class="file pdf icon"></i>
                                <span>Leaderboard PDF</span>
                            </a>
                            <div class="ui compact menu leaderboard-export-menu">
                                <div class="ui simple dropdown item leaderboard-export-trigger">
                                    <i class="download icon"></i>
                                    <span>Export</span>
                                    <i class="dropdown icon"></i>
                                    <div class="menu">
                                        <a href="{URLS.COMPETITION_GET_ZIP(competition.id)}" target="new" class="item">All CSV</a>
                                        <a href="{URLS.COMPETITION_GET_JSON(competition.id)}" target="new" class="item">All JSON</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                <!-- If there's no leaderboard, show this message -->
                <div show="{_.isEmpty(competition.leaderboards)}">
                    <div class="center aligned"><h2>No visible leaderboard for this benchmark</h2></div>
                </div>
                <!-- Else, show the leaderboard -->
                <div show="{!_.isEmpty(competition.leaderboards)}">
                    <leaderboards class="leaderboard-table"
                              phase_id="{ self.selected_phase_index }"
                              is_admin="{competition.admin}">
                    </leaderboards>
                </div>
            </div>
        </div>
    </div>

    <script>
        var self = this

        self.competition = {}
        self.files = {}
        self.selected_phase_index = undefined
        self.leaderboard_phases = []
        self.loading = true

        self.on('mount', function () {
            $('.tabular.menu.details-menu .item', self.root).tab({
                history: true,
                historyType: 'hash',
            })
        })

        CODALAB.events.on('competition_loaded', function (competition) {
            self.competition = competition
            self.competition.files = []
            _.forEach(competition.phases, phase => {
                _.forEach(phase.tasks, task => {
                    // Over complicated data org but it is so we can order exactly how we want...
                    let input_data = {}
                    let reference_data = {}
                    let ingestion_program = {}
                    let scoring_program = {}
                    _.forEach(task.public_datasets, dataset => {
                        let type = 'input_data'
                        if(dataset.type === "input_data"){
                            type = 'Input Data'
                            input_data = {key: dataset.key, name: dataset.name, file_size: dataset.file_size, phase: phase.name, task: task.name, type: type, available: self.competition.make_input_data_available}
                        }else if(dataset.type === "reference_data"){
                            type = 'Reference Data'
                            reference_data = {key: dataset.key, name: dataset.name, file_size: dataset.file_size, phase: phase.name, task: task.name, type: type, available: false}
                        }else if(dataset.type === "ingestion_program"){
                            type = 'Ingestion Program'
                            ingestion_program = {key: dataset.key, name: dataset.name, file_size: dataset.file_size, phase: phase.name, task: task.name, type: type, available: self.competition.make_programs_available}
                        }else if(dataset.type === "scoring_program"){
                            type = 'Scoring Program'
                            scoring_program = {key: dataset.key, name: dataset.name, file_size: dataset.file_size, phase: phase.name, task: task.name, type: type, available: self.competition.make_programs_available}
                        }
                    })
                    if(self.competition.participant_status === 'approved' && self.competition.make_programs_available){
                        Object.keys(ingestion_program).length != 0 ? self.competition.files.push(ingestion_program) : null
                        Object.keys(scoring_program).length != 0 ? self.competition.files.push(scoring_program) : null
                    }if(self.competition.participant_status === 'approved' && self.competition.make_input_data_available){
                        Object.keys(input_data).length != 0 ? self.competition.files.push(input_data) : null
                    }
                    if(self.competition.admin && !self.competition.make_programs_available){
                        Object.keys(ingestion_program).length != 0 ? self.competition.files.push(ingestion_program) : null
                        Object.keys(scoring_program).length != 0 ? self.competition.files.push(scoring_program) : null
                    }
                    if(self.competition.admin && !self.competition.make_input_data_available){
                        Object.keys(input_data).length != 0 ? self.competition.files.push(input_data) : null
                    }
                    if(self.competition.admin){
                        Object.keys(reference_data).length != 0 ? self.competition.files.push(reference_data) : null
                    }

                })
                // Need code for public_data and starting_kit at phase level
                if(self.competition.participant_status === 'approved'){
                    _.forEach(phase.tasks, task => {
                        _.forEach(task.solutions, solution => {
                            soln = {
                                key: solution.data,
                                name: solution.name,
                                file_size: solution.size,
                                phase: phase.name,
                                task: task.name,
                                type: 'Solution',
                                available: true
                            }
                            Object.keys(solution).length != 0 ? self.competition.files.push(soln) : null
                        })
                    })
                    if (phase.starting_kit != null){
                        s_kit = {
                            key: phase.starting_kit.key,
                            name: phase.starting_kit.name,
                            file_size: phase.starting_kit.file_size,
                            phase: phase.name,
                            task: '-',
                            type: 'Starting Kit',
                            available: true
                        }
                        Object.keys(phase.starting_kit).length != 0 ? self.competition.files.push(s_kit) : null
                    }
                    if (phase.public_data != null){
                        p_data = {
                            key: phase.public_data.key,
                            name: phase.public_data.name,
                            file_size: phase.public_data.file_size,
                            phase: phase.name,
                            task: '-',
                            type: 'Public Data',
                            available: true
                        }
                        Object.keys(phase.public_data).length != 0 ? self.competition.files.push(p_data) : null
                    }
                }
            })
            // loop over competition phases to mark if phase has started or ended
            self.competition.phases.forEach(function (phase, index) {

                phase_ended = false
                phase_started = false

                // check if phase has started
                if((Date.parse(phase["start"]) - Date.parse(new Date())) > 0){
                    // start date is in the future, phase started = NO
                    phase_started = false
                }else{
                    // start date is not in the future, phase started = YES
                    phase_started = true
                }

                if(phase_started){
                    // check if end data exists for this phase
                    if(phase["end"]){
                        if((Date.parse(phase["end"]) - Date.parse(new Date())) < 0){
                            // Phase cannote accept submissions if end date is in the past
                            phase_ended = true
                        }else{
                            // Phase can accept submissions if end date is in the future
                            phase_ended = false
                        }
                    }else{
                        // Phase can accept submissions if end date is not given
                        phase_ended = false
                    }
                }
                self.competition.phases[index]["phase_ended"] = phase_ended
                self.competition.phases[index]["phase_started"] = phase_started
            })

            self.competition.is_admin = CODALAB.state.user.has_competition_admin_privileges(competition)

            // Find current phase and set selected phase index to its id
            self.selected_phase_index = _.get(_.find(self.competition.phases, {'status': 'Current'}), 'id')

            // If no Current phase in this competition
            // Find Final phase and set selected phase index to its id
            if (self.selected_phase_index == null) {
                self.selected_phase_index = _.get(_.find(self.competition.phases, {is_final_phase: true}), 'id')
            }

            // If no Final phase in this competition
            // Find the last phase and set selected phase index to its id
            if (self.selected_phase_index == null) {
                self.selected_phase_index = self.competition.phases[self.competition.phases.length - 1].id;
            }

            self.phase_selected(_.find(self.competition.phases, {id: self.selected_phase_index}))

            $('.phases-tab .accordion', self.root).accordion()

            $('.tabular.pages-menu.menu .item', self.root).tab()

            // Need to run update() to build tags to render html in
            self.update()

            try {
                _.forEach(self.competition.pages, (page, index) => {
                    // Render html pages
                    const rendered_content = renderMarkdownWithLatex(page.content)
                    const page_el = $(`#page_${index}`)[0]
                    if (page_el) {
                        page_el.innerHTML = ""
                        rendered_content.forEach(node => {
                            page_el.appendChild(node.cloneNode(true)) // Append each node
                        })
                    }
                })
            } catch (e) {
                console.error('[comp-tabs] Error rendering page content:', e)
            }

            try {
                if (self.competition_has_no_terms_page()) {
                    const rendered_content = renderMarkdownWithLatex(self.competition.terms)
                    const term_el = $(`#page_term`)[0]
                    if (term_el) {
                        term_el.innerHTML = ""
                        rendered_content.forEach(node => {
                            term_el.appendChild(node.cloneNode(true)) // Append each node
                        })
                    }
                }
            } catch (e) {
                console.error('[comp-tabs] Error rendering terms:', e)
            }

            try {
                _.forEach(self.competition.phases, (phase, index) => {
                    // Render phase description
                    const rendered_content = renderMarkdownWithLatex(phase.description)
                    const phase_el = $(`#phase_${index}`)[0]
                    if (phase_el) {
                        phase_el.innerHTML = ""
                        rendered_content.forEach(node => {
                            phase_el.appendChild(node.cloneNode(true)) // Append each node
                        })
                    }
                })
            } catch (e) {
                console.error('[comp-tabs] Error rendering phase descriptions:', e)
            }

            _.delay(() => {
                self.loading = false
                self.update()
            }, 500)
        })

        self.competition_has_no_terms_page = function () {
            var no_term_page = true
            if(self.competition.pages){
                self.competition.pages.forEach(function (page) {
                    if (page.title === "Terms") {
                        no_term_page = false
                    }
                })
            }
            return no_term_page
        }

        CODALAB.events.on('phase_selected', function (selected_phase) {
            self.selected_phase = selected_phase
            self.update()
        })

        self.pretty_date = function (date_string) {
            if (date_string != null) {
                return luxon.DateTime.fromISO(date_string).toLocaleString(luxon.DateTime.DATETIME_FULL)
            } else {
                return ''
            }
        }

        self.phase_selected = function (data, event) {
            if(data) {
                self.selected_phase_index = data.id
                self.update()
                CODALAB.events.trigger('phase_selected', data)
            }
        }

        self.get_phase_leaderboard_pdf_url = function () {
            if (!self.selected_phase_index) {
                return "#"
            }
            return `/api/phases/${self.selected_phase_index}/leaderboard-pdf/`
        }

        self.get_sample_submission_url = function () {
            return `/api/competitions/${self.competition.id}/sample-submission/`
        }

        self.update()


    </script>

    <style type="text/stylus">
        $blue = #2c3f4c
        $teal = #00bbbb
        $lightblue = #f2faff

        .leaderboard-table
            overflow auto

        .comp-tabs
            max-width 1240px
            margin 0 auto 56px !important
            padding 0 24px

        .ui.grid.comp-tabs
            width 100%

        .ui.secondary.pointing.menu .active.item
            border-color #1d5aa7
            color #163a67

        .ui.secondary.pointing.menu .active.item:hover
            border-color #1d5aa7
            color #163a67

        .inline
            display inline-block

        .leaderboard-pdf-button
            margin-right 0 !important
            display inline-flex !important
            align-items center
            gap 8px
            border-radius 999px !important
            padding 12px 18px !important
            box-shadow 0 12px 24px rgba(16, 41, 71, 0.10)

        .resources-message
            margin-bottom 18px !important

        .resources-group
            margin-top 14px

        .resources-group:first-of-type
            margin-top 10px

        .resources-group-title
            font-size 13px
            font-weight 700
            color #35577d
            margin-bottom 8px

        .resource-buttons
            margin-top 10px
            flex-wrap wrap

        .details-menu
            width 100%
            display flex !important
            align-items center
            gap 8px
            padding 12px 14px
            margin 0 0 22px !important
            border-radius 20px
            background linear-gradient(180deg, #ffffff, #f6faff)
            border 1px solid rgba(27, 63, 106, 0.08)
            box-shadow 0 18px 36px rgba(16, 41, 71, 0.06)

        .details-menu .item
            font-size 15px
            font-weight 700
            color #4f6788 !important
            border-radius 12px !important
            padding 12px 16px !important
            transition background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease

        .details-menu .active.item, .details-menu .item
            margin 0 !important
            cursor pointer

        .details-menu .active.item
            background rgba(29, 90, 167, 0.1) !important
            box-shadow inset 0 -2px 0 #1d5aa7

        .details-menu .item:hover
            background rgba(29, 90, 167, 0.06) !important
            color #163a67 !important

        .home-tab
            padding 2em 0.5em

            .short-description
                font-size 44px
                font-weight 600
                color $blue
                line-height 1em

            .seven.column
                align-self center


            .long-description
                border-left solid 2px $teal
                color $blue
                font-size 14px
                padding 10px
                font-family 'Overpass Mono', monospace

            .leaderboard
                width 100%
                text-align center
                color $blue
                font-family 'Overpass Mono', monospace

                table
                    color $blue !important

                    thead > tr > th
                        color $blue !important
                        background-color $lightblue !important

                    .medal
                        height 25px
                        width auto


        .submission-tab
            margin 0 auto
            width 100%
            background #fff
            border-radius 26px
            border 1px solid rgba(27, 63, 106, 0.08)
            box-shadow 0 18px 34px rgba(16, 41, 71, 0.06)
            padding 24px

            .button-container
                display flex
                flex-wrap wrap
                gap 10px
                margin-bottom 18px

                .ui.button
                    border-radius 999px
                    background #eef5fb
                    color #1d5aa7
                    border 1px solid rgba(29, 90, 167, 0.12)
                    box-shadow none
                    font-weight 700

                .ui.button.active
                    background linear-gradient(180deg, #1d5aa7, #133f77)
                    color #fff

        .results-tab
            margin 0 auto
            width 100%
            background #fff
            border-radius 26px
            border 1px solid rgba(27, 63, 106, 0.08)
            box-shadow 0 18px 34px rgba(16, 41, 71, 0.06)
            padding 24px

            .button-container
                display flex
                flex-wrap wrap
                gap 10px
                margin-bottom 20px

                .ui.button
                    border-radius 999px
                    background #eef5fb
                    color #1d5aa7
                    border 1px solid rgba(29, 90, 167, 0.12)
                    box-shadow none
                    font-weight 700

                .ui.button.active
                    background linear-gradient(180deg, #1d5aa7, #133f77)
                    color #fff

            .results-shell
                width 100%

            .leaderboard-topbar
                display flex
                justify-content space-between
                align-items flex-start
                flex-wrap wrap
                gap 16px
                margin-bottom 18px

            .leaderboard-phase-group
                margin-bottom 0
                flex 1 1 480px

            .leaderboard-admin-actions
                display flex
                align-items center
                justify-content flex-end
                flex-wrap wrap
                gap 10px
                flex 0 0 auto
                margin-left auto

            .leaderboard-export-menu
                margin 0 !important
                border none !important
                box-shadow none !important
                background transparent !important

            .leaderboard-export-trigger
                display inline-flex !important
                align-items center
                gap 8px
                border-radius 999px !important
                padding 12px 16px !important
                background #f7fbff !important
                border 1px solid rgba(29, 90, 167, 0.12) !important
                color #1d5aa7 !important
                font-weight 700 !important
                box-shadow 0 10px 22px rgba(16, 41, 71, 0.06)

            .leaderboard-export-trigger .icon
                margin 0 !important

            .leaderboard-export-trigger > .menu
                margin-top 8px !important
                right 0 !important
                left auto !important
                border-radius 16px !important
                overflow hidden
                border 1px solid rgba(27, 63, 106, 0.10) !important
                box-shadow 0 18px 34px rgba(16, 41, 71, 0.10) !important

        .pages-tab
            margin 0 auto
            width 100%
            background #fff
            border-radius 26px
            border 1px solid rgba(27, 63, 106, 0.08)
            box-shadow 0 18px 34px rgba(16, 41, 71, 0.06)
            padding 28px

            .ui.vertical.tabular.menu.pages-menu
                width 100% !important
                padding-right 10px
                border none

            .vertical.tabular.menu > .item
                cursor pointer
                border-radius 14px !important
                color #547092
                margin-bottom 10px
                background #f7fbff
                border 1px solid rgba(27, 63, 106, 0.08)
                font-weight 700

            .vertical.tabular.menu > .active.item
                z-index 1
                background linear-gradient(180deg, #1d5aa7, #133f77)
                color #fff !important
                border-color transparent

            .twelve.wide.column .tab.active
                z-index 0
                background-color white
                margin 0
                padding 10px 0 0
                border none

        .phases-tab
            margin 0 auto
            width 100%
            color #2c3f4c
            background #fff
            border-radius 26px
            border 1px solid rgba(27, 63, 106, 0.08)
            box-shadow 0 18px 34px rgba(16, 41, 71, 0.06)
            padding 28px

            .underline
                border-bottom 1px solid $teal
                display inline-block
                line-height 0.9em

            .ui.segments
                font-family 'Overpass Mono', monospace
                font-size 14px

            .ui.styled.accordion
                width 100%
                border-radius 18px
                border 1px solid rgba(27, 63, 106, 0.08)
                overflow hidden

            .phase-header
                font-family 'Roboto', sans-serif
                font-size 20px !important
                text-transform none
                font-weight 600
                background-color #f6faff
                color #12365f !important

            .ui.styled.accordion .phase-header.active
                color #12365f !important
                border-bottom solid 1px rgba(27, 63, 106, 0.08) !important
                background rgba(29, 90, 167, 0.10) !important

            .phase-header:hover
                color #12365f !important
                background rgba(29, 90, 167, 0.08) !important

            .phase-label
                font-size 15px
                font-weight 600
                font-family 'Roboto', sans-serif
                color #1d5aa7
                text-transform uppercase

            .phase-info
                margin-bottom 10px

            .content.active
                background #fff

        .admin-tab
            margin 0 auto
            width 100%

        pre
            background #f4f4f4
            border 1px solid #ddd
            border-left 3px solid $teal
            border-radius 6px
            color #666
            page-break-inside avoid
            font-family monospace
            font-size 0.85em
            line-height 1.6
            margin-bottom 1.6em
            max-width 100%
            overflow auto
            padding 1em 1.5em
            display block
            word-wrap break-word

        .ui.table
            color $blue !important

            thead > tr > th
                color $blue !important
                background-color $lightblue !important

            .medal
                height 25px
                width auto

        @media only screen and (max-width: 767px)
            .comp-tabs
                padding 0 16px

            .details-menu
                flex-wrap wrap

            .details-menu .right.menu
                width 100%
                justify-content flex-end

            .pages-tab,
            .phases-tab,
            .submission-tab,
            .results-tab
                padding 18px

            .results-tab .leaderboard-topbar
                align-items stretch

            .results-tab .leaderboard-admin-actions
                width 100%
                justify-content flex-start
                margin-left 0

    </style>
</comp-tabs>
