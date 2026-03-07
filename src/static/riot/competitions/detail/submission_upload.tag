<submission-upload>
    <div class="ui sixteen wide column submission-container">

        <div class="submission-form">
            <div class="ui grid middle aligned">
                <div class="sixteen wide column">
                    <h1 style="margin: 0;">Submission upload</h1>
                </div>
            </div>

            <div if="{_.get(selected_phase, 'status') === 'Previous'}" class="ui red message">
                This phase has ended and no longer accepts submissions!
            </div>

            <div if="{_.get(selected_phase, 'status') === 'Next'}" class="ui yellow message">
                This phase hasn't started yet!
            </div>

            <form class="ui form coda-animated {error: errors}" ref="form" enctype="multipart/form-data">

                <div class="submission-form" ref="fact_sheet_form" if="{ opts.fact_sheet !== null}">
                    <h2>Metadata or Fact Sheet</h2>
                    <div class="submission-form-question" each="{ question in opts.fact_sheet }">

                        <span if="{ question.type === 'text' }">
                            <label if="{question.is_required == 'true'}" class="required-answer">{ question.title }:</label>
                            <label if="{question.is_required == 'false'}">{ question.title }:</label>
                            <input type="text" name="{ question.key }">
                        </span>

                        <span if="{ question.type === 'checkbox' }">
                            <label>{ question.title }:</label>
                            <input type="hidden" name="{ question.key }" value="false">
                            <input type="checkbox" name="{ question.key }" value="true">
                        </span>

                        <span if="{ question.type === 'selection' }">
                            <label if="{question.is_required == 'true'}" class="required-answer">{ question.title }:</label>
                            <label if="{question.is_required == 'false'}">{ question.title }:</label>
                            <select class="ui dropdown" name="{ question.key }">
                                <option value="">Select</option>
                                <option each="{ option in question.options }" value="{ option }">{ option }</option>
                            </select>
                        </span>

                    </div>
                </div>

                <div class="field" if="{ organizations && organizations.length }">
                    <label>Organization</label>
                    <select class="ui dropdown" ref="organization_dropdown">
                        <option value="">None</option>
                        <option each="{ org in organizations }" value="{ org.id }">{ org.name }</option>
                        <option value="new_organization">+ Add New Organization</option>
                    </select>
                </div>

                <!-- MODEL CARD SECTION -->
                <div class="field submission-upload-section">
                    <p>
                        Please download the template, complete it, convert it to <b>PDF</b>,
                        and upload it together with your prediction submission.
                    </p>

                    <button class="ui basic button" type="button" onclick="{download_model_card_template}">
                        Download Model Card Template
                    </button>

                    <div class="upload-block">
                        <label class="upload-label">
                            Model Card PDF
                        </label>
                        <input-file
                            name="model_card_file"
                            ref="model_card_file"
                            error="{errors.model_card_file}"
                            accept=".pdf">
                        </input-file>
                    </div>
                </div>

                <!-- PREDICTION FILE SECTION -->
                <div class="field submission-upload-section">
                    <div class="upload-block">
                        <label class="upload-label">
                            Prediction ZIP
                        </label>
                        <input-file
                            name="data_file"
                            ref="data_file"
                            error="{errors.data_file}"
                            accept=".zip">
                        </input-file>
                    </div>
                </div>

            </form>

        </div>

        <div class="ui indicating progress" ref="progress">
            <div class="bar">
                <div class="progress">{ upload_progress }%</div>
            </div>
        </div>

        <div class="ui styled fluid accordion submission-output-container">

            <div class="title active">
                <i class="dropdown icon"></i>
                Submission logs
            </div>

            <div class="content active">

                <div id="submission-output" ref="submission_output" class="ui segment coda-animated">

                    <div class="submission-tabs ui top attached tabular menu">
                        <a class="item active" onclick="{select_tab}" data-tab="prediction">Prediction</a>
                        <a class="item" onclick="{select_tab}" data-tab="scoring">Scoring</a>
                    </div>

                    <div class="ui bottom attached tab segment active" data-tab="prediction">
                        <log_window
                            selected_submission="{selected_submission}"
                            selected_tab="prediction"
                            detailed_result_url="{detailed_result_urls[selected_submission.id]}"
                            show_graph="{opts.competition.enable_detailed_results}">
                        </log_window>
                    </div>

                    <div class="ui bottom attached tab segment" data-tab="scoring">
                        <log_window
                            selected_submission="{selected_submission}"
                            selected_tab="scoring"
                            detailed_result_url="{detailed_result_urls[selected_submission.id]}"
                            show_graph="{opts.competition.enable_detailed_results}">
                        </log_window>
                    </div>

                    <div class="ui checkbox" ref="autoscroll_checkbox" style="margin-top: 10px;">
                        <input type="checkbox" onchange="{toggle_autoscroll}">
                        <label>Auto-scroll logs</label>
                    </div>

                </div>

            </div>

        </div>

    </div>

<script>

    var self = this

    self.download_model_card_template = function (e) {
        if (e) { e.preventDefault() }
        window.open("/static/model-cards/model_card_template.docx", "_blank")
    }

    self.errors = {}
    self.selected_submission = {}
    self.selected_phase = {}
    self.selected_tasks = []
    self.upload_progress = 0
    self.autoscroll_selected = false
    self.children = []
    self.organizations = []

    self.on("mount", function () {
        if (self.refs.organization_dropdown) {
            $(self.refs.organization_dropdown).dropdown()
        }
    })

    self.toggle_autoscroll = function () {
        self.autoscroll_selected = !self.autoscroll_selected
        self.autoscroll_output()
    }

    self.select_tab = function (e) {
        var tab = e.item.getAttribute('data-tab')
        $('.submission-tabs .item', self.root).removeClass('active')
        $(e.item).addClass('active')
        $('.tab.segment', self.root).removeClass('active')
        $('.tab.segment[data-tab="' + tab + '"]', self.root).addClass('active')
    }

    CODALAB.events.on('submission_selected', function (selected_submission) {
        self.selected_submission = selected_submission
        self.autoscroll_output()
    })

    self.autoscroll_output = function () {
        if (!self.refs.autoscroll_checkbox) {
            return
        }
        if (self.autoscroll_selected) {
            var output = self.refs.submission_output
            output.scrollTop = output.scrollHeight
        }
    }

</script>

<style type="text/stylus">

:scope
    display block
    width 100%
    height 100%
    margin-bottom 15px

.required-answer::after
    margin -.2em 0 0 .2em
    content '*'
    color #db2828

.submission-form
    background-color white
    padding 2em
    border solid 1px #dcdcdcdc
    margin-bottom 2em

.submission-form-question
    padding .66em 2em

    label
        font-size 16px
        font-weight 600

.submission-upload-section
    margin-top 2em
    margin-bottom 2em

.upload-block
    margin-top 1em

.upload-label
    display block
    font-size 14px
    font-weight 600
    margin-bottom .5em

#submission-output

    .submission-tabs
        overflow-x scroll
        padding-bottom 10px

        .item
            border solid 1px #efefef
            cursor pointer

            &:hover
                background-color #f5f5f5

        .item.active
            border solid 1px #03bbbbad

code
    background hsl(220, 80%, 90%)

.submission-container
    margin-top 1em

.hidden
    display none

.submission-output-container
    margin-top 15px

    .ui.basic.segment
        min-height 300px
        display none
        overflow-y auto

.graph-container
    display block
    height 250px

</style>

</submission-upload>