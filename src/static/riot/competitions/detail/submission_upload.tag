<submission-upload>
    <div class="ui sixteen wide column submission-container">

        <div class="submission-form">
            <div class="submission-head">
                <div class="submission-kicker">Submit</div>
                <div class="ui grid middle aligned">
                    <div class="sixteen wide column">
                        <h1 style="margin: 0;">Upload a new submission</h1>
                        <p class="submission-intro">
                            Add the required ZIP file, complete any required metadata, and submit to the active test phase.
                            If this benchmark allows model card file uploads, the template downloads will appear directly in this submit panel.
                        </p>
                    </div>
                </div>
            </div>

            <div if="{_.get(selected_phase, 'status') === 'Previous'}" class="ui red message">
                This phase has ended and no longer accepts submissions!
            </div>

            <div if="{_.get(selected_phase, 'status') === 'Next'}" class="ui yellow message">
                This phase hasn't started yet!
            </div>

            <form class="ui form {error: errors}" ref="form" enctype="multipart/form-data">

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

                    <!-- Model card section — only shown when the competition requires it -->
                    <div class="upload-block model-card-block" if="{ opts.competition && opts.competition.enable_model_card_submission }">
                        <label class="upload-label">
                            Model Card
                            <span class="mc-required-star">*</span>
                        </label>

                        <div class="mc-helper-text">
                            Provide the model card using the submission format enabled for this benchmark.
                        </div>

                        <div class="mc-template-box" if="{ supports_mc_upload() }">
                            <div class="mc-template-title">Model Card Templates</div>
                            <div class="ui small buttons resource-buttons">
                                <a class="ui button"
                                   href="/static/model-cards/model_card_template.docx"
                                   target="_blank"
                                   rel="noopener noreferrer">
                                    <i class="download icon"></i>
                                    DOCX Template
                                </a>
                                <a class="ui button"
                                   href="/static/model-cards/model_card_template.json"
                                   target="_blank"
                                   rel="noopener noreferrer">
                                    <i class="download icon"></i>
                                    JSON Template
                                </a>
                                <a class="ui button"
                                   href="/static/model-cards/model_card_template.md"
                                   target="_blank"
                                   rel="noopener noreferrer">
                                    <i class="download icon"></i>
                                    Markdown Template
                                </a>
                            </div>
                        </div>

                        <!-- Tab switcher -->
                        <div class="ui secondary pointing menu mc-tab-menu" if="{ supports_mc_form() && supports_mc_upload() }">
                            <a class="item { active: mc_mode === 'form' }"
                               onclick="{ set_mc_mode_form }">
                                Fill Form
                            </a>
                            <a class="item { active: mc_mode === 'upload' }"
                               onclick="{ set_mc_mode_upload }">
                                Upload File
                            </a>
                        </div>

                        <!-- Form fill mode -->
                        <div class="mc-panel" if="{ supports_mc_form() && mc_mode === 'form' }">
                            <div class="mc-field">
                                <label>Model Name <span class="mc-required-star">*</span></label>
                                <input class="mc-input" type="text" ref="mc_model_name" placeholder="e.g. Cox-PH Baseline">
                            </div>
                            <div class="mc-field">
                                <label>Task <span class="mc-required-star">*</span></label>
                                <input class="mc-input" type="text" ref="mc_task" placeholder="e.g. Survival prediction">
                            </div>
                            <div class="mc-field">
                                <label>Output <span class="mc-required-star">*</span></label>
                                <input class="mc-input" type="text" ref="mc_output" placeholder="e.g. Risk score per horizon (1–60 months)">
                            </div>
                            <div class="mc-field">
                                <label>Overview <span class="mc-required-star">*</span></label>
                                <textarea class="mc-textarea" ref="mc_overview" rows="4"
                                    placeholder="Briefly describe the purpose of the model and the problem it is designed to solve."></textarea>
                            </div>
                            <!-- ── Optional fields toggle ─────────────────── -->
                            <div class="mc-optional-toggle" onclick="{ toggle_optional }">
                                <i class="{ show_optional ? 'caret down' : 'caret right' } icon" style="font-size:11px;"></i>
                                Optional Fields
                            </div>

                            <!-- Optional fields — hidden/shown via display:none (show), keeps DOM nodes so refs stay readable -->
                            <div class="mc-optional-section" show="{ show_optional }">

                                <div class="mc-section-header">Model Details</div>
                                <div class="mc-field">
                                    <label>Algorithm</label>
                                    <input class="mc-input" type="text" ref="mc_algorithm"
                                        placeholder="e.g. Discrete-Time Hazard model with logit link">
                                </div>
                                <div class="mc-field">
                                    <label>Loss Function</label>
                                    <input class="mc-input" type="text" ref="mc_loss_function"
                                        placeholder="e.g. Logistic log-loss with L2 regularization">
                                </div>
                                <div class="mc-field">
                                    <label>Training Procedure</label>
                                    <textarea class="mc-textarea" ref="mc_training_procedure" rows="3"
                                        placeholder="Describe how the model was trained, validated, and any hyperparameter tuning."></textarea>
                                </div>

                                <div class="mc-section-header">Data</div>
                                <div class="mc-field">
                                    <label>Data Source</label>
                                    <textarea class="mc-textarea" ref="mc_data_source" rows="2"
                                        placeholder="Describe where the training data comes from."></textarea>
                                </div>
                                <div class="mc-field">
                                    <label>Target Variable</label>
                                    <textarea class="mc-textarea" ref="mc_data_target" rows="2"
                                        placeholder="Describe the prediction target / label."></textarea>
                                </div>
                                <div class="mc-field">
                                    <label>Features <span class="mc-hint">— one per line</span></label>
                                    <textarea class="mc-textarea" ref="mc_data_features" rows="4"
                                        placeholder="Numeric firm-level predictors&#10;Identifier columns excluded: CompNo, yyyy, mm&#10;Discrete time variable (month) added"></textarea>
                                </div>
                                <div class="mc-field">
                                    <label>Data Frequency</label>
                                    <input class="mc-input" type="text" ref="mc_data_frequency"
                                        placeholder="e.g. Monthly observations">
                                </div>
                                <div class="mc-field">
                                    <label>Preprocessing Steps <span class="mc-hint">— one per line</span></label>
                                    <textarea class="mc-textarea" ref="mc_data_preprocessing" rows="4"
                                        placeholder="Median imputation to numeric predictors&#10;Standardization of numeric predictors&#10;One-hot encode month variable"></textarea>
                                </div>

                                <div class="mc-section-header">Evaluation</div>
                                <div class="mc-field">
                                    <label>Primary Metric</label>
                                    <input class="mc-input" type="text" ref="mc_eval_primary"
                                        placeholder="e.g. Mean ROC-AUC across requested prediction horizons">
                                </div>
                                <div class="mc-field">
                                    <label>Secondary Metrics</label>
                                    <input class="mc-input" type="text" ref="mc_eval_secondary"
                                        placeholder="e.g. Horizon-specific ROC-AUC (1, 3, 6, 12, 24, 36, 48, 60 months)">
                                </div>

                                <div class="mc-section-header">Additional Information</div>
                                <div class="mc-field">
                                    <label>Limitations <span class="mc-hint">— one per line</span></label>
                                    <textarea class="mc-textarea" ref="mc_limitations" rows="4"
                                        placeholder="Assumes discrete monthly time intervals&#10;Only numeric features are used&#10;May perform poorly with sparse event rates"></textarea>
                                </div>
                                <div class="mc-field">
                                    <label>Intended Use</label>
                                    <textarea class="mc-textarea" ref="mc_intended_use" rows="2"
                                        placeholder="Describe the intended use case and any restrictions."></textarea>
                                </div>
                                <div class="mc-field">
                                    <label>Interpretability</label>
                                    <textarea class="mc-textarea" ref="mc_interpretability" rows="2"
                                        placeholder="Explain how the model's predictions can be interpreted."></textarea>
                                </div>

                            </div><!-- /mc-optional-section -->

                            <div class="mc-error" if="{ errors.model_card_form_data }">{ errors.model_card_form_data }</div>
                        </div>

                        <!-- File upload mode -->
                        <div class="mc-panel" if="{ supports_mc_upload() && mc_mode === 'upload' }">
                            <div style="font-size:12px; color:rgba(0,0,0,.5); margin-bottom:6px;">
                                Accepted formats: .pdf &nbsp;·&nbsp; .json &nbsp;·&nbsp; .md / .markdown
                            </div>
                            <input-file
                                name="model_card_file"
                                ref="model_card_file"
                                error="{errors.model_card_file}"
                                accept=".pdf,application/pdf,.json,.md,.markdown">
                            </input-file>
                        </div>
                    </div>
                </div>

        <div class="field submit-action-row" style="margin-top: 24px;">
            <button
                type="button"
                class="ui button submit-primary-btn"
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

    </div>

<script>
    var self = this
    self.mixin(ProgressBarMixin)

    self.errors = {}
    self.selected_submission = {}
    self.selected_phase = {}
    self.selected_tasks = []
    self.upload_progress = 0
    self.children = []
    self.organizations = []
    self.is_submitting = false

    // 'form' = fill-in-page, 'upload' = file upload
    self.mc_mode = 'form'

    self.get_mc_submission_mode = function () {
        return _.get(opts, 'competition.model_card_submission_mode') || 'both'
    }

    self.supports_mc_form = function () {
        var mode = self.get_mc_submission_mode()
        return mode === 'form' || mode === 'both'
    }

    self.supports_mc_upload = function () {
        var mode = self.get_mc_submission_mode()
        return mode === 'file' || mode === 'both'
    }

    self.sync_mc_mode = function () {
        if (!self.supports_mc_form() && self.supports_mc_upload()) {
            self.mc_mode = 'upload'
        } else if (self.supports_mc_form()) {
            self.mc_mode = 'form'
        }
    }

    self.show_optional = false
    self.toggle_optional = function () {
        self.show_optional = !self.show_optional
        self.update()
    }

    self.set_mc_mode_form = function () {
        if (!self.supports_mc_form()) return
        self.mc_mode = 'form'
        self.update()
    }

    self.set_mc_mode_upload = function () {
        if (!self.supports_mc_upload()) return
        self.mc_mode = 'upload'
        self.update()
    }

    self.on("mount", function () {
        console.log("[submission-upload] mounted")
        console.log("[submission-upload] opts.competition =", opts.competition)
        console.log("[submission-upload] opts.fact_sheet =", opts.fact_sheet)
        self.sync_mc_mode()

        if (self.refs.organization_dropdown) {
            $(self.refs.organization_dropdown).dropdown()
        }
    })

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

        // Clear model card form fields
        if (self.refs.mc_model_name) self.refs.mc_model_name.value = ''
        if (self.refs.mc_task)       self.refs.mc_task.value = ''
        if (self.refs.mc_output)     self.refs.mc_output.value = ''
        if (self.refs.mc_overview)   self.refs.mc_overview.value = ''

        self.sync_mc_mode()
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

        var mc_required = opts.competition && opts.competition.enable_model_card_submission
        var allow_mc_form = self.supports_mc_form()
        var allow_mc_upload = self.supports_mc_upload()
        if (mc_required) {
            if (self.mc_mode === 'upload') {
                if (!allow_mc_upload) {
                    self.errors.model_card_file = "This benchmark only accepts model card form submissions"
                }
                // File upload mode
                else if (!model_card_file) {
                    self.errors.model_card_file = "Please select a model card file"
                } else {
                    var mc_name = model_card_file.name.toLowerCase()
                    var mc_ok = mc_name.endsWith('.pdf') || mc_name.endsWith('.json') ||
                                mc_name.endsWith('.md') || mc_name.endsWith('.markdown')
                    if (!mc_ok) {
                        self.errors.model_card_file = "Accepted: .pdf, .json, .md, .markdown"
                    }
                }
            } else {
                if (!allow_mc_form) {
                    self.errors.model_card_form_data = "This benchmark only accepts model card file uploads"
                }
                // Form fill mode
                var mc_model_name = self.refs.mc_model_name ? self.refs.mc_model_name.value.trim() : ''
                var mc_task       = self.refs.mc_task       ? self.refs.mc_task.value.trim()       : ''
                var mc_output     = self.refs.mc_output     ? self.refs.mc_output.value.trim()     : ''
                var mc_overview   = self.refs.mc_overview   ? self.refs.mc_overview.value.trim()   : ''
                var mc_missing = []
                if (!mc_model_name) mc_missing.push('Model Name')
                if (!mc_task)       mc_missing.push('Task')
                if (!mc_output)     mc_missing.push('Output')
                if (!mc_overview)   mc_missing.push('Overview')
                if (mc_missing.length) {
                    self.errors.model_card_form_data = "Please fill in: " + mc_missing.join(', ')
                }
            }
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
        console.log("[submission-upload] mc_mode =", self.mc_mode)

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

            var mc_required = opts.competition && opts.competition.enable_model_card_submission
            var allow_mc_form = self.supports_mc_form()
            var allow_mc_upload = self.supports_mc_upload()

            console.log("[submission-upload] upload prediction_input =", prediction_input)
            console.log("[submission-upload] upload prediction_file =", prediction_file)
            console.log("[submission-upload] upload prediction size =", prediction_file ? prediction_file.size : null)
            console.log("[submission-upload] upload prediction type =", prediction_file ? prediction_file.type : null)
            console.log("[submission-upload] upload mc_required =", mc_required)
            console.log("[submission-upload] upload mc_mode =", self.mc_mode)
            console.log("[submission-upload] upload model_card_input =", model_card_input)
            console.log("[submission-upload] upload model_card_file =", model_card_file)

            if (!prediction_file) {
                console.error("[submission-upload] No prediction file found inside upload()")
                self.errors.data_file = "Please select a submission ZIP file"
                self.is_submitting = false
                self.update()
                return
            }

            var mc_form_data_json = null
            if (mc_required && self.mc_mode === 'form' && allow_mc_form) {
                // Helper: trim a ref's value or return null
                function _str(ref) {
                    return (self.refs[ref] && self.refs[ref].value.trim()) || null
                }
                // Helper: split textarea lines into array, or null if empty
                function _lines(ref) {
                    var raw = self.refs[ref] && self.refs[ref].value.trim()
                    if (!raw) return null
                    var items = raw.split('\n').map(function (l) { return l.trim() }).filter(Boolean)
                    return items.length ? items : null
                }

                // Required fields
                var card = {
                    model_name: self.refs.mc_model_name ? self.refs.mc_model_name.value.trim() : '',
                    task:       self.refs.mc_task       ? self.refs.mc_task.value.trim()       : '',
                    output:     self.refs.mc_output     ? self.refs.mc_output.value.trim()     : '',
                    overview:   self.refs.mc_overview   ? self.refs.mc_overview.value.trim()   : ''
                }

                // Optional: Model Details
                var model_obj = {}
                if (_str('mc_algorithm'))          model_obj.algorithm          = _str('mc_algorithm')
                if (_str('mc_loss_function'))       model_obj.loss_function      = _str('mc_loss_function')
                if (_str('mc_training_procedure')) model_obj.training_procedure = _str('mc_training_procedure')
                if (Object.keys(model_obj).length) card.model = model_obj

                // Optional: Data
                var data_obj = {}
                if (_str('mc_data_source'))          data_obj.source        = _str('mc_data_source')
                if (_str('mc_data_target'))          data_obj.target        = _str('mc_data_target')
                if (_lines('mc_data_features'))      data_obj.features      = _lines('mc_data_features')
                if (_str('mc_data_frequency'))       data_obj.frequency     = _str('mc_data_frequency')
                if (_lines('mc_data_preprocessing')) data_obj.preprocessing = _lines('mc_data_preprocessing')
                if (Object.keys(data_obj).length)    card.data = data_obj

                // Optional: Evaluation
                var eval_obj = {}
                if (_str('mc_eval_primary'))   eval_obj.primary_metric    = _str('mc_eval_primary')
                if (_str('mc_eval_secondary')) eval_obj.secondary_metrics = _str('mc_eval_secondary')
                if (Object.keys(eval_obj).length) card.evaluation = eval_obj

                // Optional: Additional
                if (_lines('mc_limitations'))    card.limitations     = _lines('mc_limitations')
                if (_str('mc_intended_use'))     card.intended_use    = _str('mc_intended_use')
                if (_str('mc_interpretability')) card.interpretability = _str('mc_interpretability')

                mc_form_data_json = JSON.stringify(card)
                console.log("[submission-upload] upload mc_form_data_json =", mc_form_data_json)
            } else if (mc_required && self.mc_mode === 'upload' && allow_mc_upload) {
                if (!model_card_file) {
                    console.error("[submission-upload] No model card file found inside upload()")
                    self.errors.model_card_file = "Please select a model card file"
                    self.is_submitting = false
                    self.update()
                    return
                }
            } else if (mc_required && self.mc_mode === 'form' && !allow_mc_form) {
                self.errors.model_card_form_data = "This benchmark only accepts model card file uploads"
                self.is_submitting = false
                self.update()
                return
            } else if (mc_required && self.mc_mode === 'upload' && !allow_mc_upload) {
                self.errors.model_card_file = "This benchmark only accepts model card form submissions"
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

                    // Attach model card payload (file or form data)
                    if (mc_form_data_json) {
                        formData.append('model_card_form_data', mc_form_data_json)
                    } else if (model_card_file) {
                        formData.append('model_card_file', model_card_file)
                    }

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
                    console.log("[submission-upload] mc_form_data =", mc_form_data_json ? "(form)" : "(none)")

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
                                    if (errors.data_file) {
                                        toastr.error(errors.data_file)
                                    }
                                    if (errors.model_card_file) {
                                        toastr.error(errors.model_card_file)
                                    }
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

    CODALAB.events.on('submission_selected', function (selected_submission) {
        console.log("[submission-upload] event submission_selected", selected_submission)
        self.selected_submission = selected_submission
        self.update()
    })

    CODALAB.events.on('phase_selected', function (selected_phase) {
        console.log("[submission-upload] event phase_selected", selected_phase)
        self.selected_phase = selected_phase
        self.update()
    })

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
    background linear-gradient(180deg, #ffffff, #fbfdff)
    padding 2em
    border 1px solid rgba(27, 63, 106, 0.10)
    border-radius 24px
    box-shadow 0 18px 34px rgba(16, 41, 71, 0.06)
    margin-bottom 2em

.submission-head
    margin-bottom 20px

.submission-kicker
    margin-bottom 8px
    color #6f87a3
    font-size 12px
    font-weight 800
    letter-spacing .12em
    text-transform uppercase

.submission-intro
    margin-top 10px
    color #6180a3
    font-size 14px
    line-height 1.6

.submission-form-question
    padding 1em 1.2em
    border-radius 16px
    background #f8fbff
    border 1px solid rgba(27, 63, 106, 0.06)
    margin-bottom 10px

    label
        font-size 15px
        font-weight 600

.submission-upload-section
    margin-top 2em
    margin-bottom 2em

.upload-block
    margin-top 1em

.upload-label
    display block
    font-size 14px
    font-weight 700
    margin-bottom .65em
    color #183d68

.model-card-block
    margin-top 1.5em
    padding 1.25em 1.3em
    border 1px solid rgba(27, 63, 106, 0.10)
    border-radius 20px
    background linear-gradient(180deg, #f8fbff, #f4f8fd)

.mc-helper-text
    margin-bottom 10px
    color #6180a3
    font-size 13px
    line-height 1.5

.mc-template-box
    margin-bottom 14px
    padding 12px 14px
    border-radius 16px
    background rgba(255,255,255,0.78)
    border 1px solid rgba(27, 63, 106, 0.08)

.mc-template-title
    margin-bottom 8px
    color #35577d
    font-size 13px
    font-weight 700

.resource-buttons
    display flex
    flex-wrap wrap
    gap 8px

.mc-required-star
    color #db2828
    margin-left 2px

.mc-tab-menu
    margin-bottom .8em !important
    font-size 13px

    .item
        border-radius 12px !important
        margin-right 8px !important
        color #587493 !important
        font-weight 700 !important

    .active.item
        background rgba(29, 90, 167, 0.10) !important
        color #184a86 !important

.mc-panel
    padding-top .75em

.mc-field
    margin-bottom 1em

    label
        font-size 13px
        font-weight 600
        display block
        margin-bottom 3px
        color rgba(0,0,0,.75)

.mc-input
    width 100%
    padding 12px 14px
    border 1px solid rgba(27, 63, 106, 0.12)
    border-radius 14px
    font-size 13px
    outline none
    background #fff
    &:focus
        border-color #4b84c4
        box-shadow 0 0 0 4px rgba(75, 132, 196, 0.12)

.mc-textarea
    width 100%
    padding 12px 14px
    border 1px solid rgba(27, 63, 106, 0.12)
    border-radius 14px
    font-size 13px
    resize vertical
    outline none
    background #fff
    &:focus
        border-color #4b84c4
        box-shadow 0 0 0 4px rgba(75, 132, 196, 0.12)

.mc-error
    color #db2828
    font-size 12px
    margin-top 4px

.mc-optional-toggle
    font-size 12px
    font-weight 600
    color rgba(0,0,0,.5)
    cursor pointer
    padding 4px 0
    margin-top 10px
    user-select none

    &:hover
        color rgba(0,0,0,.75)

.mc-optional-section
    margin-top 10px
    padding-top 10px
    border-top 1px solid rgba(27, 63, 106, .08)

.mc-section-header
    font-size 11px
    font-weight 700
    text-transform uppercase
    letter-spacing .05em
    color #6b84a1
    border-bottom 1px solid rgba(27, 63, 106, .08)
    padding-bottom 6px
    margin-top 12px
    margin-bottom 10px

.mc-hint
    font-weight 400
    font-size 11px
    color rgba(0,0,0,.4)

code
    background hsl(220, 80%, 90%)

.submission-container
    margin-top 1em

.hidden
    display none

.submit-action-row
    display flex
    justify-content flex-start

.submit-primary-btn
    min-width 160px
    padding 14px 22px !important
    border-radius 999px !important
    background linear-gradient(135deg, #ffb347, #f28c18) !important
    color #fff !important
    font-weight 800 !important
    box-shadow 0 14px 28px rgba(242, 140, 24, 0.22) !important

    &[disabled]
        opacity .55 !important
        box-shadow none !important

.graph-container
    display block
    height 250px
</style>

</submission-upload>
