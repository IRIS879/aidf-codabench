<comp-detail-header>
    <section class="detail-hero-shell">
        <div class="detail-hero-copy">
            <div class="detail-hero-kicker">
                <span class="status-dot"></span>
                { get_kicker_text() }
            </div>
            <h1 class="detail-hero-title">{ competition.title }</h1>
            <p class="detail-hero-summary">{ get_summary_text() }</p>

            <div class="detail-hero-meta">
                <span>Managed by <a href="/profiles/user/{competition.created_by}" target="_BLANK">{competition.owner_display_name}</a></span>
                <span>{ competition.submissions_count || 0 } submissions</span>
                <span>{ get_phase_badge_text() }</span>
            </div>

            <div if="{ competition.forum_enabled }" class="detail-hero-links">
                <button class="hero-action-link" onclick="{open_forum}">
                    Discussion
                </button>
            </div>

            <div if="{competition.admin}" class="detail-admin-actions">
                <a href="{URLS.COMPETITION_EDIT(competition.id)}" class="detail-admin-link">Edit</a>
                <button class="detail-admin-link" onclick="{show_modal.bind(this, '.manage-participants.modal')}">Participants</button>
                <button class="detail-admin-link" onclick="{show_modal.bind(this, '.manage-submissions.modal')}">Submissions</button>
                <button class="detail-admin-link" onclick="{show_modal.bind(this, '.manage-competition.modal')}">Dumps</button>
                <button class="detail-admin-link" onclick="{show_modal.bind(this, '.migration.modal')}">Migrate</button>
            </div>
        </div>

        <aside class="detail-hero-aside">
            <div class="detail-logo-panel">
                <div class="detail-logo-wrap">
                    <img if="{competition.logo}" class="detail-logo-image" alt="Competition Logo" src="{ competition.logo }">
                    <div if="{!competition.logo}" class="detail-logo-placeholder">
                        { get_logo_initials() }
                    </div>
                </div>
                <div class="detail-logo-caption">Test Preview</div>
            </div>

            <div class="detail-stat-grid">
                <div class="detail-stat-card">
                    <div class="detail-stat-label">Submissions</div>
                    <div class="detail-stat-value">{ competition.submissions_count || 0 }</div>
                </div>
                <div class="detail-stat-card">
                    <div class="detail-stat-label">Participants</div>
                    <div class="detail-stat-value">{ competition.participants_count || 0 }</div>
                </div>
                <div class="detail-stat-card wide">
                    <div class="detail-stat-label">Current phase</div>
                    <div class="detail-stat-value compact">{ get_current_phase_name() }</div>
                </div>
            </div>

            <div if="{competition.report}" class="detail-info-panel">
                <div class="detail-info-row">
                    <span class="detail-info-label">Report</span>
                    <span class="detail-info-value mono" id="report-url">{ competition.report }</span>
                    <button class="copy-mini" onclick="{copy_report_url}" title="Copy report URL">
                        <i class="ui copy icon"></i>
                    </button>
                </div>
            </div>
        </aside>
    </section>

    <!-- Manage Competition Modal -->
    <div class="ui manage-competition modal" ref="files_modal">
        <div class="content">
            <div class="ui dropdown button">
                <i class="download icon"></i>
                <div class="text">Create Competition Dump</div>
                <div class="menu">
                    <div class="parent-modal item" onclick="{create_dump.bind(this, true)}">
                        Dump with keys
                    </div>
                    <div class="parent-modal item" onclick="{create_dump.bind(this, false)}">
                        Dump with files
                    </div>
                </div>
            </div>
            <button class="ui icon button" onclick="{update_files}">
                <i class="sync alternate icon"></i> Refresh Table
            </button>
            <table class="ui table">
                <thead>
                <tr>
                    <th>Files</th>
                </tr>
                </thead>
                <tbody>
                <tr show="{files.bundle}">
                    <td class="selectable">
                        <a href="{files.bundle ? files.bundle.url : ''}">
                            <i class="file archive outline icon"></i>
                            Bundle: {files.bundle ? files.bundle.name : ''}
                        </a>
                    </td>
                </tr>
                <tr each="{file in files.dumps}" show="{files.dumps}">
                    <td class="selectable">
                        <a href="{file.url}">
                            <i class="file archive outline icon"></i>
                            Dump: {file.name}
                        </a>
                    </td>
                </tr>
                <tr>
                    <td show="{!files.dumps && !files.bundle}">
                        <em>No Files Yet</em>
                    </td>
                </tr>
                <tr>
                    <td class="center aligned" if="{tr_show}">Generating Dump, Please Refresh</td>
                </tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Manage Submissions Modal -->
    <div class="ui manage-submissions large modal" ref="sub_modal">
        <div class="content">
            <submission-manager admin="{competition.admin}" competition="{ competition }"></submission-manager>
        </div>
    </div>

    <!-- Manage Participants Modal -->
    <div class="ui manage-participants modal" ref="participant_modal">
        <div class="content">
            <participant-manager></participant-manager>
        </div>
    </div>

    <!-- Manual Migration Modal -->
    <div class="ui migration modal" ref="migration_modal">
        <div class="content">
            <table class="ui table">
                <thead>
                <tr>
                    <th colspan="100%">Please Choose a phase to migrate</th>
                </tr>
                </thead>
                <tbody>
                <tr each="{phase, index in competition.phases}">
                    <td>{phase.name}</td>
                    <td class="collapsing">
                        <button if="{index !== competition.phases.length - 1}" class="ui button" onclick="{migrate_phase.bind(this, phase.id)}">
                            Migrate
                        </button>
                    </td>
                </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let self = this

        self.competition = {}
        self.files = []
        self.tr_show = false

        CODALAB.events.on('competition_loaded', function (competition) {
            competition.admin = CODALAB.state.user.has_competition_admin_privileges(competition)
            self.competition = competition
            self.update()
            if (self.competition.admin) {
                self.update_files()
            }
            $('.dropdown', self.root).dropdown()
        })

        self.close_modal = selector => $(selector).modal('hide')
        self.show_modal = selector => $(selector).modal('show')

        self.open_forum = function () {
            window.location.href = URLS.FORUM(self.competition.forum)
        }

        self.create_dump = (keys_instead_of_files) => {
            CODALAB.api.create_competition_dump(self.competition.id, keys_instead_of_files)
                .done(data => {
                    self.tr_show = true
                    toastr.success("Success! Your competition dump is being created.")
                    self.update()
                })
                .fail(response => {
                    toastr.error("Error trying to create competition dump.")
                })
        }

        self.update_files = () => {
            CODALAB.api.get_competition_files(self.competition.id)
                .done(data => {
                    self.files = data
                    self.tr_show = false
                    self.update()
                })
                .fail(response => {
                    toastr.error('Error Retrieving Competition Files')
                })
        }

        self.copy_report_url = function () {
            let range = document.createRange()
            range.selectNode(document.getElementById("report-url"))
            window.getSelection().removeAllRanges()
            window.getSelection().addRange(range)
            document.execCommand("copy")
            window.getSelection().removeAllRanges()
        }

        self.get_summary_text = function () {
            const summary = (self.competition.description || '').trim()
            if (summary) {
                return summary
            }
            const firstPage = _.get(self.competition, 'pages[0].content', '')
            if (firstPage) {
                return firstPage.replace(/[#>*`_\-\n]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 180) + '...'
            }
            return 'Review the task setup, submit artifacts, and inspect results from one cleaner evaluation page.'
        }

        self.get_current_phase = function () {
            return _.find(self.competition.phases, {status: 'Current'}) || _.find(self.competition.phases, {is_final_phase: true}) || _.head(self.competition.phases)
        }

        self.get_current_phase_name = function () {
            const phase = self.get_current_phase()
            return phase ? phase.name : 'Not available'
        }

        self.get_phase_badge_text = function () {
            const phase = self.get_current_phase()
            if (!phase) {
                return 'Schedule not available'
            }
            return phase.end ? `${phase.name} ends ${pretty_date(phase.end)}` : `${phase.name} is open`
        }

        self.get_kicker_text = function () {
            const phase = self.get_current_phase()
            return phase ? `AIDF TEST · ${phase.status}` : 'AIDF TEST'
        }

        self.get_logo_initials = function () {
            const words = (self.competition.title || 'AIDF Test').split(/\s+/).filter(Boolean)
            return words.slice(0, 2).map(word => word.charAt(0)).join('').toUpperCase()
        }

        self.migrate_phase = function (phase_id) {
            CODALAB.api.manual_migration(phase_id)
                .done(data => {
                    toastr.success("Migration of this phase to the next should begin soon.")
                    self.close_modal(self.refs.migration_modal)
                })
                .fail(error => {
                    toastr.error('Something went wrong trying to migrate this phase.')
                })
        }
    </script>

    <style type="text/stylus">
        .detail-hero-shell
            max-width 1240px
            margin 32px auto 18px
            padding 0 24px
            display grid
            grid-template-columns minmax(0, 1.5fr) 360px
            align-items start
            gap 24px

        .detail-hero-copy
            padding 18px 0 0

        .detail-hero-kicker
            display inline-flex
            align-items center
            gap 10px
            padding 8px 14px
            border-radius 999px
            background rgba(31, 78, 145, 0.08)
            color #234c88
            font-size 12px
            font-weight 700
            letter-spacing 0.12em
            text-transform uppercase

        .status-dot
            width 8px
            height 8px
            border-radius 50%
            background #f59f00
            box-shadow 0 0 0 6px rgba(245, 159, 0, 0.15)

        .detail-hero-title
            margin 16px 0 12px
            color #102947
            font-size 46px
            line-height 1.08
            font-weight 800

        .detail-hero-summary
            max-width 760px
            margin 0
            color #557195
            font-size 17px
            line-height 1.65

        .detail-hero-meta
            display flex
            flex-wrap wrap
            gap 10px 18px
            margin-top 18px
            color #4f6788
            font-size 14px
            font-weight 600

            a
                color #1b4f92

        .detail-hero-links
            display flex
            flex-wrap wrap
            align-items center
            gap 12px
            margin-top 26px

        .hero-action-link
            padding 0
            background transparent
            color #184a86
            font-size 15px
            font-weight 700
            border none
            cursor pointer
            transition color 0.2s ease, transform 0.2s ease

        .hero-action-link:hover
            transform translateY(-1px)
            color #0f3c72

        .detail-admin-actions
            display flex
            flex-wrap wrap
            gap 10px
            margin-top 18px

        .detail-admin-link
            padding 8px 12px
            border-radius 999px
            border 1px solid rgba(24, 74, 134, 0.12)
            background #fff
            color #335882
            font-size 13px
            font-weight 700
            cursor pointer

        .detail-hero-aside
            display flex
            flex-direction column
            gap 16px

        .detail-logo-panel,
        .detail-info-panel
            background #fff
            border 1px solid rgba(28, 84, 149, 0.1)
            border-radius 26px
            box-shadow 0 20px 40px rgba(27, 63, 106, 0.08)

        .detail-logo-panel
            padding 18px

        .detail-logo-wrap
            display flex
            align-items center
            justify-content center
            min-height 188px
            border-radius 20px
            background linear-gradient(180deg, #f7fbff, #edf4fb)
            border 1px solid rgba(27, 63, 106, 0.08)

        .detail-logo-image
            max-width 100%
            max-height 150px
            object-fit contain

        .detail-logo-placeholder
            width 108px
            height 108px
            border-radius 28px
            display flex
            align-items center
            justify-content center
            background linear-gradient(135deg, #1d5aa7, #133f77)
            color #fff
            font-size 34px
            font-weight 800

        .detail-logo-caption
            margin-top 12px
            color #5e7899
            font-size 13px
            text-align center
            letter-spacing 0.08em
            text-transform uppercase

        .detail-stat-grid
            display grid
            grid-template-columns repeat(2, minmax(0, 1fr))
            gap 14px

        .detail-stat-card
            padding 18px 18px 20px
            border-radius 20px
            background linear-gradient(180deg, #1d5aa7, #133f77)
            color #fff
            box-shadow 0 16px 28px rgba(19, 63, 119, 0.18)

        .detail-stat-card.wide
            grid-column 1 / -1

        .detail-stat-label
            font-size 12px
            letter-spacing 0.08em
            text-transform uppercase
            color rgba(255, 255, 255, 0.74)

        .detail-stat-value
            margin-top 8px
            font-size 28px
            line-height 1.15
            font-weight 800

        .detail-stat-value.compact
            font-size 20px

        .detail-info-panel
            padding 18px

        .detail-info-row
            display grid
            grid-template-columns 90px minmax(0, 1fr) auto
            gap 10px
            align-items start
            padding 12px 0
            border-bottom 1px solid rgba(27, 63, 106, 0.08)

        .detail-info-row:last-child
            border-bottom none

        .detail-info-label
            color #7390b1
            font-size 12px
            font-weight 800
            letter-spacing 0.08em
            text-transform uppercase

        .detail-info-value
            color #233e5e
            font-size 13px
            line-height 1.6
            word-break break-word

        .detail-info-value.mono
            font-family 'Consolas', 'Monaco', monospace

        .copy-mini
            width 30px
            height 30px
            border none
            border-radius 10px
            background #eef5fb
            color #1d5aa7
            cursor pointer

        @media only screen and (max-width: 1024px)
            .detail-hero-shell
                grid-template-columns 1fr

        @media only screen and (max-width: 767px)
            .detail-hero-shell
                padding 0 16px

            .detail-hero-title
                font-size 34px

            .detail-hero-summary
                font-size 16px

            .detail-stat-grid
                grid-template-columns 1fr

            .detail-stat-card.wide
                grid-column auto

            .detail-info-row
                grid-template-columns 1fr
    </style>
</comp-detail-header>
