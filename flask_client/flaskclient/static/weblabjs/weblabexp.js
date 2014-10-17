// From StackOverflow. To extract parameters from the URL (not the hash)
(function ($) {
    $.QueryString = (function (a) {
        if (a == "") return {};
        var b = {};
        for (var i = 0; i < a.length; ++i) {
            var p = a[i].split('=');
            if (p.length != 2) continue;
            b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
        }
        return b;
    })(window.location.search.substr(1).split('&'))
})(jQuery);


/**
 *
 * WEBLAB EXP MODULE
 *
 * WeblabExp is a library that provides a simple way to interact
 * with Weblab experiments.
 *
 * It supports two modes:
 *
 *  FRAME MODE: The laboratory which makes use of this module is meant to run from within the Weblab page,
 *  on an iframe. The laboratory can be loaded without a reserve, and the Weblab page notifies through the
 *  onStart() callbacks whenever the reserve succeeds.
 *
 *  FREE MODE: The laboratory which makes use of this module is meant to run on its own page. The laboratory cannot
 *  be loaded before the reserve is done (because, as of now, reserves through this API are not supported).
 *
 * The mode will be automatically guessed, though it can be forced by specifying it on the WeblabExp constructor.
 *
 * @example:
 * // Instance WeblabExp in FREE mode.
 * weblabExp = new WeblabExp(false);
 *
 * It relies on jQuery-style deferred callbacks, and is thus
 * dependent on the jQuery library.
 *
 * DEPENDENCIES: jQuery
 *
 *
 * Constructor.
 *
 * @param {bool} [frameMode]: This parameter is strictly optional. If not set (undefined) then the mode will be
 * guessed automatically. If set to TRUE, the mode will be set to the FRAME MODE. If false, it will be set to the
 * FREE MODE.
 *
 */
WeblabExp = function (frameMode) {

    ///////////////////////////////////////////////////////////////
    //
    // PRIVATE ATTRIBUTES AND FUNCTIONS
    // The API uses these internally to provide an easier to use,
    // higher level API. Users of this class do not need to be
    // aware of them.
    //
    ///////////////////////////////////////////////////////////////

    /**
     * FRAME mode if true, FREE mode if false.
     * @type : bool
     */
    var mFrameMode;

    this.CORE_URL = ""; // Will be initialized through setTargetURLToStandard()
    var mReservation; // Must be set through setReservation()

    // To store callbacks for the start
    var mOnStartPromise = $.Deferred();

    // To store callbacksf or the end
    var mOnFinishPromise = $.Deferred();

    var mStartHandlers = [];
    var mFinishHandlers = [];


    /**
     * Guesses the frame mode depending on the availability of the ReserveID.
     * @returns {bool}: The mode (true if frame mode).
     * @private
     */
    this._guessFrameMode = function() {
        // TODO: For now we only support the frame-mode.
        return true;
    }


    /**
     * Checks whether the WeblabExp instance is set to FRAME MODE.
     * @returns {bool} TRUE if the current mode is FRAME MODE. FALSE if the current mode is FREE MODE.
     */
    this.isFrameMode = function() {
        return mFrameMode;
    }


    /**
     * Sets the target URL to which the AJAX requests will be directed. This is the
     * URL of the Core server's JSON handler.
     * @param {str} target_url: URL of the core server.
     *
     * Note that by default requests will be directed to the standard Weblab instance,
     * that is, to the Weblab instance located at //www.weblab.deusto.es/weblab. These
     * can also be explicitly reset through setTargetURLToStandard.
     * @see setTargetURLToStandard
     *
     * Note also that testing target URL (for use with launch_samples.py or with the
     * test script which relies on it) can also be set easily through setTargetURLToTesting.
     * @see setTargetURLToTesting
     *
     * Note that if running from a local file (file:// protocol) http:// will be preppended
     * to the URLs.
     */
    this.setTargetURLToStandard = function(target_url) {
        this.CORE_URL = target_url;

        // For making testing possible from local files (after the various security settings
        // have been disabled).
        if(window.location != undefined) {
            if(window.location.protocol != undefined && window.location.protocol === "file:") {
                if(this.CORE_URL.indexOf("://") == -1)
                    this.CORE_URL = "http:" + this.CORE_URL;
            }
        }
    }

    /**
     * Sets the target URLs to the standard ones. That is, the ones that will work
     * on the main Weblab instance, which is at //www.weblab.deusto.es.
     */
    this.setTargetURLToStandard = function() {
        this.CORE_URL = "//www.weblab.deusto.es/weblab/json/";
    }

    /**
     * Sets the target URL to the one that can be used for local automated testing. That is,
     * the ones that will work with a local Weblab instance started through the launch_sample
     * configuration, which is the one typically used for development.
     */
    this.setTargetURLToTesting = function() {
        this.CORE_URL = "http://localhost:18345";
    }

    /**
     * Sets the reservation id to use.
     *
     * @param {str} reservation_id: The reservation ID to use.
     */
    this.setReservation = function(reservation_id) {
        mReservation = reservation_id;
    }



    // !!!!!!!!!!!!!!
    // AS OF NOW, RESERVATION-EXTRACTING IS NOT SUPPORTED. THESE FUNCTIONS MUST BE REVISED.
    // !!!!!!!!!!!!!!

    //! Extracts the reservation id from the URL (in the hash).
    //!
    //! @return The reservation ID if present in the URL's hash field, or undefined.
    this._extractReservation = function () {
        mReservation = $.QueryString["reservation"];
    };

    //! Extracts the targeturl from the URL (in the hash). This is the URL towards which
    //! the AJAX requests will be directed. If not specified through the URL, then
    //! it will use a default (<location>/weblab/json/).
    this._extractTargetURL = function () {
        mTargetURL = $.QueryString["targeturl"];
        if (mTargetURL == undefined)
            mTargetURL = document.location.origin + "/weblab/json/";
    };




    /**
     * Polls the server to check the status of the experiment.
     * This is a private method, intended to just poll the server and report the response.
     * The response is not acted upon. That is, even if the experiment finished, no callbacks
     * will be called (other than the response callback itself).
     *
     * @returns {$.Promise} Promise with .done(result) and .fail(error) callbacks.
     *
     * @private
     */
    this._poll = function () {
        var promise = $.Deferred();
        var request = {"method": "poll", "params": {"reservation_id": {"id": mReservation}}};

        this._send(request)
            .done(function (success) {
                console.log("Data received: " + success);
                console.log(success);
                promise.resolve(success);
            })
            .fail(function (error) {
                promise.reject(error);
            });

        return promise.promise();
    }; // !_poll


    /**
     * Internal send function. It will send the request to the target URL.
     * Meant only for internal use. If an error occurs (network error, "is_exception" to true, or other) then
     * the exception will be printed to console, and nothing else will happen (as of now).
     *
     * @param request: The JSON-able to send. This method will not check whether the format of the JSON-able is
     * right or not. It is assumed it is. This should be a JSON-able object and NOT a JSON string.
     *
     * @return: Promise, whose .done(result_field) or .fail will be invoked depending on the success of the request.
     *
     * @private
     *
     */
    this._send = function (request) {

        var promise = $.Deferred();

        if (typeof(request) !== 'object') {
            console.error("[_SEND]: Request parameter should be an object.");
            return;
        }

        $.ajax({
            "type": "POST",
            "url": this.CORE_URL,
            "data": JSON.stringify(request),
            "dataType": "json",
            "contentType": "application/json"
        })
            .done(function (success, status, jqXHR) {
                // Example of a response: {"params":{"reservation_id":{"id":"2da9363c-c5c4-4905-9f22-817cbdf1e397;2da9363c-c5c4-4905-9f22-817cbdf1e397.default-route-to-server"}}, "method":"get_reservation_status"}

                // Check that the internal is_exception is set to false.
                if (success["is_exception"] === true) {

                    console.error("[ERROR][_send]: Returned exception (is_exception is true)");
                    console.error(success);

                    promise.reject(success);
                    return;
                }

                var result = success["result"];

                if (result == undefined) {
                    console.error("[ERROR][_send]: Response didn't contain the expected 'result' key.");
                    console.error(success);

                    promise.reject(success);
                    return;
                }

                // The request, whatever it contains, was apparently successful. We call the success handler, passing
                // the result field.
                promise.resolve(result, status, jqXHR);
            })
            .fail(function (fail) {
                console.error("[ERROR][_send]: Could not carry out the POST request to the target URL: " + this.CORE_URL);
                console.error(fail);

                promise.reject(fail);
            });

        return promise;

    }; // !_send




    /**
     * Internal method to send a command to the server.
     *
     * @param {str} command: The command to send.
     * @returns {$.Promise} Promise with .done(result) and .fail(error). Result is the "result" key within the response.
     *
     * @example
     * Example of a send_command result:
     * {"result": {"commandstring": "{\"blue\": true, \"white\": true, \"red\": true, \"yellow\": true}"}, "is_exception": false}
     *
     * @private
     */
    this._send_command = function (command) {
        var promise = $.Deferred();
        var request = {"method": "send_command", "params": {"command": {"commandstring": command}, "reservation_id": {"id": mReservation}}};

        this._send(request)
            .done(function(success_data) {
                console.log("Data received: " + success_data);
                console.log(success_data);
                promise.resolve(success_data);
            })
            .fail(function(error) {
                promise.reject(error);
            });

        return promise.promise();
    }; // !_send_command


    /**
     * Internal method to finish the experiment.
     *
     * @returns {$.Promise} Promise with .done(result) and .fail(error). Result is the "result" key within the response.
     *
     * @private
     */
    this._finished_experiment = function () {
        var promise = $.Deferred();
        var request = {"method": "finished_experiment", "params": {"reservation_id": {"id": mReservation}}};

        this._send(request)
            .done(function (success_data) {
                console.log("Data received: " + success_data);
                console.log(success_data);

                // Invoke the finish handlers.
                for (var i = 0; i < mFinishHandlers; i++) {
                    mFinishHandlers[i]();
                }

                // Clear the finish handlers so that they are not invoked again.
                mFinishHandlers = [];

                promise.resolve(success_data);
            })
            .fail(function(error){
                promise.reject(error);
            });

        return promise;
    };


    ///////////////////////////////////////////////////////////////
    //
    // PUBLIC INTERFACE
    // The following methods are part of the public interface of this
    // class. They can be used freely. Several of them rely on callbacks.
    // They might not work properly if they are run stand-alone, on a
    // context different than Weblab-Deusto.
    //
    ///////////////////////////////////////////////////////////////


    /**
     * Sends a command to the experiment server.
     * @param {str} command: The command to send.
     * @returns {$.Promise} Promise with {@link sendCommand~done} and .fail(error) as callbacks.
     *
     * @example
     * this.sendCommand("TURN_LED ON")
     *   .done(function(result) {
     *      console.log("LED IS: " + result);
     *   })
     *   .fail(function(error) {
     *      console.log("Failed to turn LED ON". Cause: " + error);
     *   });
     */
    this.sendCommand = function (command) {

        var promise = $.Deferred();

        this._send_command(command)
            .done(function(success) {
                promise.resolve(success.commandstring);
            })
            .fail(function(error) {
                promise.reject(error);
            });

        return promise.promise();
    };

    /**
     * @callback sendCommand~done
     * @param {str} response: Response to the command
     */


    //! Sends a command to the experiment server and prints the result to console.
    //! If the command was successful it is printed to the stdout and otherwise to stderr.
    //!
    //! @param text: Command to send.

    /**
     * Sends a command to the experiment server and prints the result to the console.
     * If the command was successful it will be printed to stdout and otherwise it
     * will be printed to stderr.
     *
     * @param {str} command: Command to send.
     * @returns {$.Promise} Promise with .done() and .fail() callbacks. Making use of it is optional.
     *
     * @example
     *  this.testCommand("TURN_LED ON");
     */
    this.testCommand = function (command) {

        var promise = $.Deferred();

        this.sendCommand(command)
            .done(function (success) {
                console.log("SUCCESS: " + success);
                promise.resolve(success);
            })
            .fail(function (error) {
                console.error("ERROR: " + error);
                promise.reject(error);
            });

        return promise.promise();
    };


    /**
     * Finishes the experiment. When the experiment is finished, the result is reported
     * through the .done() callback, but also through the standard onFinish callbacks,
     * which can be set through onFinish.
     * @see onFinish
     *
     * The .done() callback will be invoked first, and then the onFinish ones. It is also
     * possible that onFinish callbacks were already invoked because of a poll() result.
     * In that case, these callbacks would NOT be invoked, but the finishExperiment done callback
     * still would.
     *
     * @returns {$.Promise} Promise with .done and .fail callbacks.
     *
     */
    this.finishExperiment = function () {

        var promise = $.Deferred();

        this._finished_experiment()
            .done(function(success) {

                // TODO: Send the right thing to the callbacks. As of now I think they just receive a JSON, which
                // isn't right. Actually the end_data seems to also be in the post-reservation message from
                // the reservation status message.

                promise.resolve(success);

                if(mOnFinishPromise.status != "resolved")
                    mOnFinishPromise.resolve(success);
            })
            .fail(function(error) {
                promise.reject(error);
            });

        return promise.promise();
    };



    /**
     * onStart( startHandler ) -> promise
     * onStart () -> promise
     *
     * Registers a start handler, which will be called when the experiment's interaction starts. Several start
     * handlers can be registered. Callbacks will be executed in FIFO order, as guaranteed by jQuery Deferred rules.
     * A start handler may not be specified. In that case, a jQuery Promise is returned, to which .done() callbacks
     * can be freely attached.
     *
     * @param {function} [startHandler]: The start handler function. Should receive the starting configuration and the time left.
     *
     * @returns {$.Promise} jQuery promise where the callbacks are stored. New callbacks can be attached through .done().
     */
    this.onStart = function( startHandler ) {
        if(startHandler != undefined) {
            mOnStartPromise.done(startHandler);
        }
        return mOnStartPromise.promise();
    }

    /**
     * @callback startHandler
     * @param {object} startingConfiguration: The starting configuration of the experiment, in JSON.
     * @param {number} timeLeft: Time left for the experiment.
     */

    /**
     * onFinish( endHandler ) -> promise
     * onFinish () -> promise
     *
     * Registers an end handler, which will be called when the experiment's interaction ends. Several end
     * handlers can be registered. Callbacks will be executed in FIFO order, as guaranteed by jQuery Deferred rules.
     * A finish handler may not be specified. In that case, a jQuery Promise is returned, to which .done() callbacks
     * can be freely attached.
     *
     * @param {function} [startHandler]: The finish handler function.
     *
     * @returns {$.Promise} jQuery promise where the callbacks are stored. New callbacks can be attached through .done().
    */
    this.onFinish = function( finishHandler ) {
        if(finishHandler != undefined) {
            mOnFinishPromise.done(finishHandler);
        }
        return mOnStartPromise.promise();
    }

    /**
     * @callback finishHandler
     * @param {str} finishData: The data returned by the experiment after finishing.
     */

    // TODO: It is not yet certain that the types for the callbacks startHandler and Finish handler are as of now accurate.
    // Revise them.







    /////////////////////////////////////////////
    // THE CODE THAT FOLLOWS IS COMMENTED OUT FOR NOW AND MOST LIKELY WOULDNT WORK AS EXPECTED
    /////////////////////////////////////////////

//    //! Indicates that we are ready and that we have registered all callbacks.
//    //! Should be called to start.
//    this.ready = function () {
//        this._get_reservation_status();
//
//
//        // Poll every minute.
//        function poller() {
//            this._poll()
//                .done(function () {
//                    window.setTimeout(poller.bind(this), 1000 * 30);
//                }.bind(this));
//        };
//        window.setTimeout(poller.bind(this), 1000 * 30);
//    };
//
//
//    ///////////////////////////////////////////////////////////////
//    //
//    // CONSTRUCTOR
//    // The following is internal code to create the object.
//    //
//    ///////////////////////////////////////////////////////////////
//
//    // Extract the reservation id from the hash.
//    this._extractReservation();
//
//    // Extract the target URL from the hash or set a default one.
//    this._extractTargetURL();
//
//    //$.cookie("weblabsessionid", "T-Go5baSwSB3SHsO.route2");

}; // !WeblabExp




