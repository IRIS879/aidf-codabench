<front-page-competitions>
    <section class="test-section">
        <div class="section-heading-row">
            <div>
                <div class="section-kicker">Latest</div>
                <div class="ui large header">Recent Tests</div>
                <p class="section-copy">A live snapshot of the most recently published tests on the platform.</p>
            </div>
            <a class="section-link" href="/competitions/public/?ordering=recent">See all tests</a>
        </div>

        <div if="{!recent_competitions}" class="loader-container popular">
            <div class="lds-ring">
                <div></div>
                <div></div>
                <div></div>
                <div></div>
            </div>
        </div>

        <div if="{recent_competitions}" class="test-card-grid">
            <a each="{competition in recent_competitions}"
               href="/competitions/{competition.id}"
               class="test-card">
                <div class="test-card-head">
                    <div class="test-card-badge-row">
                        <div class="test-card-badge test-card-badge-light">Recent</div>
                        <div if="{competition.is_featured}" class="test-card-badge">Featured</div>
                    </div>
                    <div class="test-card-date">{formatDate(competition.created_when)}</div>
                </div>

                <div class="test-card-body">
                    <div class="test-card-logo" if="{competition.logo || competition.logo_icon}">
                        <img riot-src="{competition.logo || competition.logo_icon}" alt="{competition.title}">
                    </div>
                    <div class="test-card-logo test-card-logo-fallback" if="{!(competition.logo || competition.logo_icon)}">
                        <span>{initials(competition.title)}</span>
                    </div>

                    <div class="test-card-copy">
                        <h3 class="test-card-title">{competition.title}</h3>
                        <div class="test-card-meta-row">
                            <span class="meta-pill">By {competition.owner_display_name || competition.created_by}</span>
                            <span class="meta-pill">Test</span>
                        </div>
                        <p class="test-card-description">{truncateDescription(competition.description)}</p>
                    </div>
                </div>

                <div class="test-card-footer">
                    <div class="test-card-stats">
                        <div class="stat-inline">
                            <strong>{competition.submissions_count || 0}</strong>
                            <span>runs</span>
                        </div>
                        <div class="stat-inline">
                            <strong>{competition.participants_count || 0}</strong>
                            <span>users</span>
                        </div>
                    </div>
                    <span class="test-card-cta">Open Test</span>
                </div>
            </a>
        </div>
    </section>

    <script>
        var self = this

        self.one("mount", function () {
            self.get_frontpage_competitions()
        })

        self.get_frontpage_competitions = function (data) {
            return CODALAB.api.get_front_page_competitions(data)
                .fail(function () {
                    toastr.error("Could not load competition list")
                })
                .done(function (data) {
                    self.recent_competitions = data["recent_comps"]
                    self.update()
                    $('.loader-container').hide()
                })
        }

        self.truncateDescription = function (description) {
            var fallback = 'Open the test page to inspect files, requirements, and the full evaluation flow.'
            if (!description) {
                return fallback
            }
            var normalized = description.replace(/\s+/g, ' ').trim()
            if (normalized.length <= 138) {
                return normalized
            }
            return normalized.slice(0, 135) + '...'
        }

        self.initials = function (title) {
            if (!title) {
                return 'T'
            }
            return title.trim().charAt(0).toUpperCase()
        }

        self.formatDate = function (value) {
            if (!value) {
                return 'Recently added'
            }
            try {
                return luxon.DateTime.fromISO(value).toFormat('dd LLL yyyy')
            } catch (e) {
                return value
            }
        }
    </script>

    <style>
        front-page-competitions {
            width: calc(100% - 48px);
            max-width: 1240px;
            margin: 0 auto;
            display: block;
            padding: 28px 0 44px;
        }

        .test-section {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        .section-heading-row {
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 1rem;
        }

        .section-kicker {
            margin-bottom: 0.45rem;
            color: #6f87aa;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.72rem;
            font-weight: 700;
        }

        .ui.large.header {
            margin: 0 !important;
            font-size: 2rem !important;
            color: #143b68 !important;
            line-height: 1.05 !important;
        }

        .section-copy {
            margin: 0.75rem 0 0;
            max-width: 760px;
            color: #68809c;
            font-size: 1rem;
            line-height: 1.65;
        }

        .section-link {
            color: #1e5cab;
            font-size: 0.98rem;
            font-weight: 700;
            text-decoration: none;
        }

        .section-link:hover {
            color: #0f4688;
            text-decoration: none;
        }

        .test-card-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 22px;
            align-items: stretch;
        }

        .test-card {
            display: flex;
            flex-direction: column;
            min-height: 320px;
            height: 100%;
            padding: 20px 20px 18px;
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 52%, #f2f8ff 100%);
            border: 1px solid #d7e4f3;
            border-radius: 24px;
            box-shadow: 0 18px 36px rgba(25, 68, 117, 0.08);
            text-decoration: none;
            transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
            position: relative;
            overflow: hidden;
        }

        .test-card::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 4px;
            background: linear-gradient(90deg, #1e5cab 0%, #4f84c1 60%, #8ab2df 100%);
            opacity: 0.95;
        }

        .test-card:hover {
            transform: translateY(-6px);
            border-color: #aac6e8;
            box-shadow: 0 24px 42px rgba(25, 68, 117, 0.14);
            text-decoration: none;
        }

        .test-card-head {
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 14px;
            margin-bottom: 16px;
        }

        .test-card-badge-row {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            flex-wrap: wrap;
        }

        .test-card-badge {
            padding: 5px 10px;
            border-radius: 999px;
            background: rgba(26, 89, 162, 0.1);
            color: #16509a;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .test-card-badge-light {
            background: rgba(244, 159, 31, 0.14);
            color: #d67c00;
        }

        .test-card-date {
            color: #7a8ea8;
            font-size: 0.82rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .test-card-body {
            display: grid;
            grid-template-columns: 60px minmax(0, 1fr);
            gap: 14px;
            align-items: start;
            flex: 1;
        }

        .test-card-logo {
            width: 60px;
            height: 60px;
            border-radius: 16px;
            background: linear-gradient(180deg, #ffffff 0%, #eef5fd 100%);
            border: 1px solid #d7e4f3;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            flex-shrink: 0;
        }

        .test-card-logo img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .test-card-logo-fallback span {
            color: #1b4f94;
            font-size: 1.3rem;
            font-weight: 800;
        }

        .test-card-copy {
            min-width: 0;
            display: grid;
            grid-template-rows: minmax(3.15rem, auto) auto minmax(6.35rem, 1fr);
            align-content: start;
        }

        .test-card-title {
            margin: 0 0 10px;
            color: #163d69;
            font-size: 1.28rem;
            line-height: 1.2;
            font-weight: 700;
            display: -webkit-box;
            overflow: hidden;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
        }

        .test-card-meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 12px;
            align-self: start;
        }

        .meta-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.34rem 0.62rem;
            border-radius: 999px;
            background: #edf4fc;
            color: #587291;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .test-card-description {
            margin: 0;
            color: #53697f;
            font-size: 0.94rem;
            line-height: 1.65;
            display: -webkit-box;
            overflow: hidden;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            min-height: calc(1.65em * 4);
        }

        .test-card-stats {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }

        .stat-inline {
            display: inline-flex;
            align-items: baseline;
            gap: 0.35rem;
            padding: 0.45rem 0.7rem;
            border-radius: 999px;
            background: #edf4fc;
            color: #68809b;
            font-size: 0.82rem;
            font-weight: 700;
        }

        .stat-inline strong {
            color: #163d69;
            font-size: 0.95rem;
        }

        .test-card-footer {
            margin-top: 18px;
            padding-top: 16px;
            border-top: 1px solid #e5eef8;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .test-card-cta {
            color: #1c5cab;
            font-weight: 700;
            font-size: 0.92rem;
        }

        @media only screen and (max-width: 1180px) {
            .test-card-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media only screen and (max-width: 900px) {
            front-page-competitions {
                width: calc(100% - 24px);
                padding: 20px 0 30px;
            }

            .ui.large.header {
                font-size: 1.7rem !important;
            }

            .test-card-grid {
                grid-template-columns: 1fr;
                gap: 16px;
            }

            .test-card-body {
                grid-template-columns: 52px minmax(0, 1fr);
            }

            .test-card-logo {
                width: 52px;
                height: 52px;
            }

            .section-heading-row {
                align-items: start;
                flex-direction: column;
            }
        }
    </style>
</front-page-competitions>
