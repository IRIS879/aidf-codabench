<comp-detail-timeline>
    <section class="phase-strip-shell" if="{ phases && phases.length }">
        <div class="phase-strip-header">
            <div>
                <div class="phase-strip-kicker">Schedule</div>
                <h3>Active test phases</h3>
            </div>
            <div class="phase-strip-note">Review dates, phase descriptions, and the active evaluation window at a glance.</div>
        </div>

        <div class="phase-strip-grid">
            <article each="{ phase in phases }" class="phase-card {current: phase.status === 'Current'} {next: phase.status === 'Next'} {previous: phase.status === 'Previous'}">
                <div class="phase-card-top">
                    <div class="phase-name">{ phase.name }</div>
                    <div class="phase-badge">{ phase.status }</div>
                </div>
                <div class="phase-dates">
                    <div><span>Start</span><strong>{ pretty_date(phase.start) }</strong></div>
                    <div><span>End</span><strong>{ phase.end ? pretty_date(phase.end) : 'No deadline' }</strong></div>
                </div>
                <p class="phase-description">{ get_phase_summary(phase) }</p>
            </article>
        </div>
    </section>

    <script>
        var self = this

        self.phases = []

        CODALAB.events.on('competition_loaded', function (competition) {
            self.phases = competition.phases || []
            self.update()
        })

        self.pretty_date = function (date_string) {
            if (!date_string) {
                return ''
            }
            return luxon.DateTime.fromISO(date_string).toLocaleString(luxon.DateTime.DATE_MED)
        }

        self.get_phase_summary = function (phase) {
            const summary = (phase.description || '').replace(/[#>*`_\-\n]/g, ' ').replace(/\s+/g, ' ').trim()
            if (summary) {
                return summary.length > 160 ? `${summary.slice(0, 157)}...` : summary
            }
            if (phase.status === 'Current') {
                return 'This phase is currently active and can accept evaluation activity based on the configured rules.'
            }
            if (phase.status === 'Next') {
                return 'This upcoming phase is prepared in advance so participants can understand the next evaluation stage.'
            }
            return 'This phase has already concluded and remains visible for schedule reference and historical context.'
        }
    </script>

    <style type="text/stylus">
        .phase-strip-shell
            max-width 1240px
            margin 10px auto 26px
            padding 0 24px

        .phase-strip-header
            display flex
            justify-content space-between
            align-items flex-end
            gap 18px
            margin-bottom 18px

            h3
                margin 6px 0 0
                color #102947
                font-size 24px
                font-weight 800

        .phase-strip-kicker
            color #6f87a3
            font-size 12px
            font-weight 800
            letter-spacing 0.12em
            text-transform uppercase

        .phase-strip-note
            max-width 460px
            color #6782a4
            font-size 14px
            line-height 1.6

        .phase-strip-grid
            display grid
            grid-template-columns repeat(auto-fit, minmax(250px, 1fr))
            gap 16px

        .phase-card
            padding 18px
            border-radius 24px
            background #fff
            border 1px solid rgba(20, 78, 146, 0.1)
            box-shadow 0 16px 34px rgba(16, 41, 71, 0.06)

        .phase-card.current
            background linear-gradient(180deg, rgba(29, 90, 167, 0.08), rgba(255, 255, 255, 1))
            border-color rgba(29, 90, 167, 0.16)

        .phase-card-top
            display flex
            justify-content space-between
            gap 12px
            align-items center

        .phase-name
            color #12365f
            font-size 20px
            font-weight 800
            line-height 1.2

        .phase-badge
            flex-shrink 0
            padding 7px 12px
            border-radius 999px
            background #edf4fb
            color #21508b
            font-size 12px
            font-weight 800
            letter-spacing 0.06em
            text-transform uppercase

        .phase-card.current .phase-badge
            background linear-gradient(135deg, #ffb347, #f28c18)
            color #fff

        .phase-dates
            display grid
            grid-template-columns repeat(2, minmax(0, 1fr))
            gap 12px
            margin-top 16px

            span
                display block
                color #8198b2
                font-size 11px
                font-weight 800
                letter-spacing 0.08em
                text-transform uppercase
                margin-bottom 4px

            strong
                color #274768
                font-size 14px
                line-height 1.5

        .phase-description
            margin 16px 0 0
            color #5a7596
            font-size 14px
            line-height 1.7

        @media only screen and (max-width: 767px)
            .phase-strip-shell
                padding 0 16px

            .phase-strip-header
                flex-direction column
                align-items flex-start

            .phase-dates
                grid-template-columns 1fr
    </style>
</comp-detail-timeline>
