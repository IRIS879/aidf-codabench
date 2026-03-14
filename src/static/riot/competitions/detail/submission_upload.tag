<submission-upload>
    <div class="ui sixteen wide column submission-container">

        <div class="submission-form">
            <div class="ui grid middle aligned">
                <div class="sixteen wide column">
                    <h1 style="margin: 0;">Submission upload</h1>
                </div>
            </div>

            <div class="ui segment" style="margin-top: 16px;">
                <div style="font-weight: 600; margin-bottom: 6px;">Model Card Template</div>
                <div style="margin-bottom: 12px; color: rgba(0,0,0,.6);">
                    Please use the official template to prepare your model card before uploading.
                </div>
                <a class="ui button"
                   style="background:#e0e1e2; color:rgba(0,0,0,.6);"
                   href="/static/model-cards/model_card_template.docx"
                   target="_blank"
                   rel="noopener noreferrer">
                    <i class="download icon"></i>
                    Download Model Card Template
                </a>
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

                <div class="field submission-upload-section">
                    <div class="upload-block">
                        <label class="upload-label">Submission ZIP</label>
                        <input-file
                            name="data_file"
                            ref="data_file"
                            error="{errors.data_file}"
                            accept=".zip">
                        </input-file>
                    </div>

                    <div class="upload-block">
                        <label class="upload-label">Model Card PDF</label>
                        <input-file
                            name="model_card_file"
                            ref="model_card_file"
                            error="{errors.model_card_file}"
                            accept=".pdf,application/pdf">
                        </input-file>
                    </div>
                </div>

        <div class="field" style="margin-top: 24px;">
            <button
                type="button"
                class="ui button"
                onclick="{check_form}"
                disabled="{is_submitting || _.get(selected_phase, 'status') !== 'Current'}">
                { is_submitting ? 'Submitting...' : 'Submit' }
            </button>
        </div>

            </form>
        </div>

        <div class="ui indicating progress" ref="progress">
            <div class="bar">
                <div class="progress">{ upload_progress }%</div>
            </div>
        </div>

        <div class="ui message error" show="{ Object.keys(errors).length > 0 }">
            <div class="header">Error(s) uploading submission</div>
            <ul class="list">
                <li each="{ error, field in errors }">
                    <strong>{ field }:</strong> { error }
                </li>
            </ul>
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
                            detailed_result_url="{get_detailed_result_url()}"
                            show_graph="{opts.competition.enable_detailed_results}">
                        </log_window>
                    </div>

                    <div class="ui bottom attached tab segment" data-tab="scoring">
                        <log_window
                            selected_submission="{selected_submission}"
                            selected_tab="scoring"
                            detailed_result_url="{get_detailed_result_url()}"
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
    self.mixin(ProgressBarMixin)

    self.errors = {}
    self.selected_submission = {}
    self.selected_phase = {}
    self.selected_tasks = []
    self.upload_progress = 0
    self.autoscroll_selected = false
    self.children = []
    self.organizations = []
    self.detailed_result_urls = {}
    self.is_submitting = false

    self.on("mount", function () {
        console.log("[submission-upload] mounted")
        console.log("[submission-upload] opts.competition =", opts.competition)
        console.log("[submission-upload] opts.fact_sheet =", opts.fact_sheet)

        if (self.refs.organization_dropdown) {
            $(self.refs.organization_dropdown).dropdown()
        }
    })

    self.get_detailed_result_url = function () {
        if (!self.selected_submission || !self.selected_submission.id) {
            return null
        }
        return self.detailed_result_urls[self.selected_submission.id] || null
    }

    self.clear_form = function () {
        console.log("[submission-upload] clear_form")

        $(':input', self.refs.form)
            .not(':button, :submit, :reset, :hidden')
            .val('')
            .removeAttr('checked')
            .removeAttr('selected')

        var prediction_input = self.refs.data_file && self.refs.data_file.refs ? self.refs.data_file.refs.file_input : null
        var model_card_input = self.refs.model_card_file && self.refs.model_card_file.refs ? self.refs.model_card_file.refs.file_input : null

        if (prediction_input) {
            prediction_input.value = ''
        }
        if (model_card_input) {
            model_card_input.value = ''
        }

        self.errors = {}
        self.update()
    }

    self.collect_fact_sheet_answers = function () {
        var answers = {}

        if (!opts.fact_sheet) {
            console.log("[submission-upload] no fact sheet configured")
            return answers
        }

        opts.fact_sheet.forEach(function (question) {
            var elements = self.refs.form.querySelectorAll('[name="' + question.key + '"]')

            if (!elements || !elements.length) {
                answers[question.key] = ''
                return
            }

            if (question.type === 'checkbox') {
                var checked = false
                for (var i = 0; i < elements.length; i++) {
                    if (elements[i].type === 'checkbox' && elements[i].checked) {
                        checked = true
                        break
                    }
                }
                answers[question.key] = checked
                return
            }

            answers[question.key] = elements[0].value
        })

        console.log("[submission-upload] fact_sheet_answers =", answers)
        return answers
    }

    self.check_form = function (event) {
        if (event) {
            event.preventDefault()
        }

        console.log("[submission-upload] CHECK_FORM fired")
        console.log("[submission-upload] selected_phase =", self.selected_phase)

        self.file_upload_progress_handler(undefined)
        self.errors = {}

        if (!self.selected_phase || self.selected_phase.status !== 'Current') {
            console.warn("[submission-upload] Phase is not current")
            toastr.warning("This phase is not accepting submissions")
            return
        }

        var prediction_input = self.refs.data_file && self.refs.data_file.refs ? self.refs.data_file.refs.file_input : null
        var prediction_file = prediction_input && prediction_input.files ? prediction_input.files[0] : null

        var model_card_input = self.refs.model_card_file && self.refs.model_card_file.refs ? self.refs.model_card_file.refs.file_input : null
        var model_card_file = model_card_input && model_card_input.files ? model_card_input.files[0] : null

        console.log("[submission-upload] prediction_input =", prediction_input)
        console.log("[submission-upload] prediction_file =", prediction_file)
        console.log("[submission-upload] prediction size =", prediction_file ? prediction_file.size : null)
        console.log("[submission-upload] prediction type =", prediction_file ? prediction_file.type : null)

        console.log("[submission-upload] model_card_input =", model_card_input)
        console.log("[submission-upload] model_card_file =", model_card_file)
        console.log("[submission-upload] model_card size =", model_card_file ? model_card_file.size : null)
        console.log("[submission-upload] model_card type =", model_card_file ? model_card_file.type : null)

        if (!prediction_file) {
            self.errors.data_file = "Please select a submission ZIP file"
        } else if (!prediction_file.name.toLowerCase().endsWith('.zip')) {
            self.errors.data_file = "Prediction file must be a .zip"
        }

        if (!model_card_file) {
            self.errors.model_card_file = "Please select a model card PDF"
        } else if (!model_card_file.name.toLowerCase().endsWith('.pdf')) {
            self.errors.model_card_file = "Model card file must be a .pdf"
        }

        if (opts.fact_sheet) {
            var fact_sheet_answers = self.collect_fact_sheet_answers()

            opts.fact_sheet.forEach(function (question) {
                var value = fact_sheet_answers[question.key]
                var isEmpty = value === '' || value === null || value === undefined

                if (question.is_required === 'true' && isEmpty) {
                    self.errors[question.key] = question.title + " is required"
                }
            })
        }

        if (Object.keys(self.errors).length > 0) {
            console.warn("[submission-upload] Form validation failed", self.errors)
            self.update()
            return
        }

        console.log("[submission-upload] CHECK_FORM passed")
        console.log("[submission-upload] phase id =", self.selected_phase && self.selected_phase.id)
        console.log("[submission-upload] prediction filename =", prediction_file && prediction_file.name)
        console.log("[submission-upload] model card filename =", model_card_file && model_card_file.name)

        self.upload()
    }

    self.upload = function () {
        try {
            console.log("[submission-upload] UPLOAD started")

            self.is_submitting = true
            self.update()

            var prediction_input = self.refs.data_file && self.refs.data_file.refs ? self.refs.data_file.refs.file_input : null
            var prediction_file = prediction_input && prediction_input.files ? prediction_input.files[0] : null

            var model_card_input = self.refs.model_card_file && self.refs.model_card_file.refs ? self.refs.model_card_file.refs.file_input : null
            var model_card_file = model_card_input && model_card_input.files ? model_card_input.files[0] : null

            console.log("[submission-upload] upload prediction_input =", prediction_input)
            console.log("[submission-upload] upload prediction_file =", prediction_file)
            console.log("[submission-upload] upload prediction size =", prediction_file ? prediction_file.size : null)
            console.log("[submission-upload] upload prediction type =", prediction_file ? prediction_file.type : null)

            console.log("[submission-upload] upload model_card_input =", model_card_input)
            console.log("[submission-upload] upload model_card_file =", model_card_file)
            console.log("[submission-upload] upload model_card size =", model_card_file ? model_card_file.size : null)
            console.log("[submission-upload] upload model_card type =", model_card_file ? model_card_file.type : null)

            if (!prediction_file) {
                console.error("[submission-upload] No prediction file found inside upload()")
                self.errors.data_file = "Please select a submission ZIP file"
                self.is_submitting = false
                self.update()
                return
            }

            if (!model_card_file) {
                console.error("[submission-upload] No model card file found inside upload()")
                self.errors.model_card_file = "Please select a model card PDF"
                self.is_submitting = false
                self.update()
                return
            }

            var timestamp = new Date().toISOString().replace(/[:.]/g, '-')

            var dataset_metadata = {
                name: timestamp + '__' + prediction_file.name,
                type: 'submission',
                description: 'Competition submission file'
            }

            console.log("[submission-upload] calling create_dataset with metadata =", dataset_metadata)

            var datasetRequest = CODALAB.api.create_dataset(
                dataset_metadata,
                prediction_file,
                self.file_upload_progress_handler
            )

            console.log("[submission-upload] create_dataset returned =", datasetRequest)

            datasetRequest
                .done(function (dataset) {
                    console.log("[submission-upload] create_dataset DONE")
                    console.log("[submission-upload] dataset upload SUCCESS")
                    console.log("[submission-upload] dataset.key =", dataset && dataset.key)
                    console.log("[submission-upload] dataset =", dataset)

                    var formData = new FormData()
                    formData.append('data', dataset.key)
                    formData.append('phase', self.selected_phase.id)
                    formData.append('model_card_file', model_card_file)

                    var fact_sheet_answers = self.collect_fact_sheet_answers()
                    if (opts.fact_sheet && Object.keys(fact_sheet_answers).length > 0) {
                        formData.append('fact_sheet_answers', JSON.stringify(fact_sheet_answers))
                    }

                    if (
                        self.refs.organization_dropdown &&
                        self.refs.organization_dropdown.value &&
                        self.refs.organization_dropdown.value !== 'new_organization'
                    ) {
                        formData.append('organization', self.refs.organization_dropdown.value)
                    }

                    console.log("[submission-upload] FINAL SUBMISSION PAYLOAD")
                    console.log("[submission-upload] phase =", self.selected_phase.id)
                    console.log("[submission-upload] dataset key =", dataset.key)
                    console.log("[submission-upload] model_card_file =", model_card_file ? model_card_file.name : null)
                    console.log("[submission-upload] model_card_size =", model_card_file ? model_card_file.size : null)

                    try {
                        for (var pair of formData.entries()) {
                            console.log("[submission-upload] formData", pair[0], pair[1])
                        }
                    } catch (e) {
                        console.error("[submission-upload] Could not iterate FormData entries", e)
                    }

                    console.log("[submission-upload] calling multipart POST /api/submissions/")

                    var submissionRequest = $.ajax({
                        url: '/api/submissions/',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        xhr: function () {
                            var xhr = $.ajaxSettings.xhr()
                            if (xhr && xhr.upload) {
                                xhr.upload.addEventListener('progress', function (evt) {
                                    if (evt.lengthComputable) {
                                        self.file_upload_progress_handler(evt)
                                    }
                                }, false)
                            }
                            return xhr
                        }
                    })

                    console.log("[submission-upload] create_submission returned =", submissionRequest)

                    submissionRequest
                        .done(function (submission) {
                            console.log("[submission-upload] create_submission DONE")
                            console.log("[submission-upload] submission =", submission)

                            toastr.success("Submission uploaded successfully")
                            self.selected_submission = submission
                            CODALAB.events.trigger('new_submission_created', submission)
                            CODALAB.events.trigger('submission_selected', submission)
                            self.clear_form()
                            self.update()
                        })
                        .fail(function (response) {
                            console.error("[submission-upload] create_submission FAIL")
                            console.error("[submission-upload] response object =", response)
                            console.error("[submission-upload] HTTP status =", response ? response.status : null)
                            console.error("[submission-upload] statusText =", response ? response.statusText : null)
                            console.error("[submission-upload] raw response =", response ? response.responseText : null)

                            if (response) {
                                try {
                                    var errors = JSON.parse(response.responseText)
                                    Object.keys(errors).forEach(function (key) {
                                        if (Array.isArray(errors[key])) {
                                            errors[key] = errors[key].join('; ')
                                        }
                                    })
                                    console.error("[submission-upload] parsed errors =", errors)
                                    self.errors = errors
                                    self.update()
                                } catch (e) {
                                    console.error("[submission-upload] create_submission FAIL parse error", e)
                                    toastr.error("Submission creation failed")
                                }
                            } else {
                                toastr.error("Submission creation failed")
                            }
                        })
                        .always(function () {
                            console.log("[submission-upload] create_submission ALWAYS")
                            self.is_submitting = false
                            setTimeout(self.hide_progress_bar, 500)
                            self.update()
                        })
                })
                .fail(function (response) {
                    console.error("[submission-upload] create_dataset FAIL")
                    console.error("[submission-upload] response object =", response)
                    console.error("[submission-upload] HTTP status =", response ? response.status : null)
                    console.error("[submission-upload] statusText =", response ? response.statusText : null)
                    console.error("[submission-upload] raw response =", response ? response.responseText : null)

                    if (response) {
                        try {
                            var errors = JSON.parse(response.responseText)
                            Object.keys(errors).forEach(function (key) {
                                if (Array.isArray(errors[key])) {
                                    errors[key] = errors[key].join('; ')
                                }
                            })
                            console.error("[submission-upload] parsed dataset errors =", errors)
                            self.errors = errors
                            self.update()
                        } catch (e) {
                            console.error("[submission-upload] create_dataset FAIL parse error", e)
                            toastr.error("Submission ZIP upload failed")
                        }
                    } else {
                        toastr.error("Submission ZIP upload failed")
                    }

                    self.is_submitting = false
                    setTimeout(self.hide_progress_bar, 500)
                    self.update()
                })
        } catch (e) {
            console.error("[submission-upload] upload crashed")
            console.error(e)
            self.is_submitting = false
            self.update()
            toastr.error("Upload crashed in browser")
        }
    }

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
        console.log("[submission-upload] event submission_selected", selected_submission)
        self.selected_submission = selected_submission
        self.autoscroll_output()
        self.update()
    })

    CODALAB.events.on('phase_selected', function (selected_phase) {
        console.log("[submission-upload] event phase_selected", selected_phase)
        self.selected_phase = selected_phase
        self.update()
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
